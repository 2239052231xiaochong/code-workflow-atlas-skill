#!/usr/bin/env node
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import path from 'node:path';
import fs from 'node:fs/promises';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const target=process.argv[2];if(!target)throw Error('Usage: node smoke_atlas.mjs /path/atlas.html [artifacts-dir]');
const output=process.argv[3];if(output)await fs.mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true,args:['--mute-audio'],...(process.env.ATLAS_BROWSER_CHANNEL?{channel:process.env.ATLAS_BROWSER_CHANNEL}:{})});
const checks=[],errors=[],requests=[];const ok=(value,label)=>{assert(value,label);checks.push(label)};
try{
const page=await browser.newPage({viewport:{width:1500,height:1000},acceptDownloads:true});page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
await page.goto(pathToFileURL(path.resolve(target)).href);const data=await page.evaluate(()=>window.workflowAtlas.data);
ok(await page.locator('.node').count()===data.phases.flatMap(p=>p.nodes||[]).length,'Main graph placement');
for(const node of data.nodes){await page.evaluate(id=>{const a=window.workflowAtlas;a.setCompare(a.data.phases.some(p=>(p.compare||[]).includes(id)));a.select(id)},node.id);ok(await page.locator('#nodeTitle').innerText()===node.title,'Selection '+node.id);if(node.sourceIds?.length){await page.locator('[data-tab="source"]').click();const first=data.sources.find(s=>s.id===node.sourceIds[0]);const fold=page.locator(`details[data-source="${first.id}"]`).first();await fold.locator('button').nth(1).click();ok(await fold.locator('[data-source-mode="raw"]').innerText()===first.text,'Exact raw source '+node.id);await fold.locator('button').nth(0).click();ok(await fold.locator('[data-source-line]').count()===first.end-first.start+1,'Original line numbers '+node.id)}if(node.promptIds?.length){await page.locator('[data-tab="prompt"]').click();for(const id of node.promptIds){const prompt=data.prompts.find(p=>p.id===id),fold=page.locator(`details[data-prompt="${id}"]`);if(prompt.assembly){await fold.locator('[data-prompt-mode="assembled"]').click();ok((await fold.innerText()).includes(prompt.assembledUser),'Assembled example '+id)}}}}
if(data.comparison){await page.evaluate(()=>window.workflowAtlas.setCompare(true));ok(await page.locator('.node').count()===data.nodes.length,'Comparison includes both lanes')}
const pending=page.waitForEvent('download');await page.locator('#export').click();const download=await pending;if(output){const file=path.join(output,'workflow-atlas.svg');await download.saveAs(file);ok((await fs.readFile(file,'utf8')).includes('<svg'),'SVG export')}
if(output)await page.screenshot({path:path.join(output,'desktop.png'),fullPage:true});
await page.setViewportSize({width:390,height:844});await page.evaluate(()=>window.workflowAtlas.setCompare(false));ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile no document overflow');ok(await page.locator('.node .title').first().evaluate(e=>parseFloat(getComputedStyle(e).fontSize)*e.getScreenCTM().a>=12),'Mobile node text remains readable');if(output)await page.screenshot({path:path.join(output,'mobile.png'),fullPage:true});
await page.locator('.node').first().focus();await page.keyboard.press('Enter');ok(await page.locator('.node.selected').count()===1,'Keyboard selection');ok(errors.length===0,'No runtime errors');ok(requests.every(url=>url.startsWith('file:')),'Offline: no network requests');
const result={passed:checks.length,checks,errors};if(output)await fs.writeFile(path.join(output,'smoke-results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await browser.close()}
