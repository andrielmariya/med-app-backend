# specialized prompts for medical extraction

METRICS_TEMPLATE = """Medical Symptoms: {symptoms}
Context: {details}

Analyze and provide exactly:
SUMMARY: (1 sentence)
SEVERITY: (1-10)
FREQUENCY: (1-10)
"""

REDFLAGS_TEMPLATE = """Medical Symptoms: {symptoms}
Context: {details}

Identify specific medical RED FLAGS (life-threatening/emergency warning signs).
Max 10 flags allowed.
If no redflags, dont add any.
Format each item exactly like this example: 
Sign - Very Short Explanation

Red Flags:"""

RISKS_TEMPLATE = """Medical Symptoms: {symptoms}
Context: {details}

Identify potential chronic risks or underlying health conditions (e.g., Diabetes, Hypertension).
Max 5.
Format each item exactly like this example:
Condition - Risk Level (Low/Medium/High)

Risks:"""

SEVERITY_TEMPLATE = """Medical Symptoms: {symptoms}
Context: {details}

Assess the SEVERITY of the situation on a scale of 1 to 10.
1 = Very Mild / Not concerning
10 = Extreme Emergency / Life-threatening

Provide exactly:
SEVERITY: (number)
"""
