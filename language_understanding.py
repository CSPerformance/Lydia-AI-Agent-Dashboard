"""Normalize conversational phrasing for intent classification, never executable text.

The original request remains the authority and is passed unchanged to tools/models.
These helpers do not rewrite file paths, commands, quotations, or stored messages.
"""
import re


def question_form(text):
    text=str(text).strip().replace('’',"'")
    for _ in range(4):
        revised=re.sub(r'^(?:(?:hey|hi|hello)[, ]+(?:lydia[, ]+)?|lydia[, :]+|please[, :]+|(?:can|could|would) you (?:please )?|(?:tell me|let me know)\s+)', '', text, flags=re.I)
        if revised==text:break
        text=revised.strip()
    contractions={"what's":"what is","what're":"what are","where's":"where is","who's":"who is","how's":"how is","why's":"why is"}
    for short,long in contractions.items():
        text=re.sub(r'^'+re.escape(short)+r'\b',long,text,flags=re.I)
    return text


def contextual_followup(text):
    text=question_form(text).lower()
    return bool(re.fullmatch(
        r"(?:explain|clarify|expand on|summarize|repeat|rephrase|say|what about|why|how so|what does) "
        r"(?:that|this|it|those)(?: part| point| step| answer| mean)?(?: again| more simply| in plain english)?[?.!]*",text)
        or re.fullmatch(r"(?:make|say|put) (?:it|that) (?:simpler|shorter|in plain english)[?.!]*",text))
