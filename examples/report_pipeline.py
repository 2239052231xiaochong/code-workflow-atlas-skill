"""Synthetic local pipeline: no network, real LLM, TTS, or private project data."""
import json

SYSTEM_TEMPLATE = "Explain only the provided material. Return JSON with a summary field."
USER_TEMPLATE = "Topic: {{topic}}\nMaterial: {{material}}"


def read_material(text):
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Material is empty")
    return cleaned


def build_prompt(topic, material):
    return SYSTEM_TEMPLATE, USER_TEMPLATE.replace("{{topic}}", topic).replace("{{material}}", material)


def demonstration_model(system, user):
    # This is deliberately a deterministic stand-in, not an external model call.
    return json.dumps({"summary": "A demonstration summary of the supplied material."})


def generate_summary(topic, material):
    system, user = build_prompt(topic, material)
    reply = demonstration_model(system, user)
    result = json.loads(reply)
    if not isinstance(result.get("summary"), str) or not result["summary"].strip():
        raise ValueError("Invalid summary")
    return result["summary"]


def make_report(summary, reused):
    return {"summary": summary, "reused": reused, "format": "json-report"}


def run(topic, material, cache):
    cleaned = read_material(material)
    key = (topic, cleaned)
    if key in cache:
        summary = cache[key]
        return make_report(summary, reused=True)
    summary = generate_summary(topic, cleaned)
    cache[key] = summary
    return make_report(summary, reused=False)
