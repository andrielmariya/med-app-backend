import os
import json
import re
from transformers import pipeline
import torch
import google.generativeai as genai
from templates import METRICS_TEMPLATE, REDFLAGS_TEMPLATE, RISKS_TEMPLATE, SEVERITY_TEMPLATE
import time

# Global references to models
_analyzer = None
_gemini_model = None

def get_analyzer():
    global _analyzer
    if _analyzer is None:
        try:
            model_path = os.path.join(os.path.dirname(__file__), "Models", "LaMini-Flan-T5-783M")
            print(f"Loading local LaMini model from {model_path}...")
            device = -1
            if torch.cuda.is_available():
                device = 0
            elif torch.backends.mps.is_available():
                device = "mps"
            
            _analyzer = pipeline('text2text-generation', model=model_path, device=device)
            print("Model loaded successfully.")
        except Exception as e:
            print(f"Failed to load local model: {e}")
            return None
    return _analyzer

def get_gemini():
    global _gemini_model
    if _gemini_model is None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("GOOGLE_API_KEY not found in environment.")
            return None
        genai.configure(api_key=api_key)
        _gemini_model = genai.GenerativeModel('gemini-flash-latest')
    return _gemini_model

def analyze_metrics(symptoms, details, model_type='local'):
    prompt = METRICS_TEMPLATE.format(symptoms=symptoms, details=details)
    print(f"[LLM] analyze_metrics requested with model: {model_type}")
    
    if model_type == 'gemini':
        model = get_gemini()
        if model:
            try:
                print("[LLM] Calling Gemini API for metrics...")
                response = model.generate_content(prompt)
                time.sleep(10)
                result = response.text
                print("[LLM] Gemini response received.")
            except Exception as e:
                print(f"[LLM] Gemini API Error (metrics): {e}")
    print(f"[LLM] analyze_metrics | Requested Model: {model_type}")
    
    if model_type == 'gemini':
        model = get_gemini()
        if not model:
            print("[LLM] ERROR: Gemini model initialization failed (API key missing?)")
            print("[LLM] Falling back to local for this call to prevent crash.")
            return analyze_metrics(symptoms, details, 'local')
            
        try:
            print("[LLM] Calling Gemini API (gemini-flash-latest)...")
            response = model.generate_content(prompt)
            time.sleep(10)
            result = response.text
            print("[LLM] Gemini SUCCESS.")
        except Exception as e:
            print(f"[LLM] Gemini API ERROR: {type(e).__name__}: {e}")
            print("[LLM] Falling back to local model.")
            return analyze_metrics(symptoms, details, 'local')
    else:
        analyzer = get_analyzer()
        if not analyzer: return "Error", {"severity": 0, "frequency": 0}
        print("[LLM] Processing with local LaMini model...")
        result = analyzer(prompt, max_length=128, do_sample=False)[0]['generated_text']
        time.sleep(10)
    
    sections = {}
    for line in result.split('\n'):
        if ':' in line:
            key, val = line.split(':', 1)
            sections[key.strip().upper()] = val.strip()
            
    summary = sections.get('SUMMARY', result)
    
    def parse(key, d):
        nums = re.findall(r'\d+', sections.get(key, ""))
        return int(nums[0]) if nums and int(nums[0]) <= 10 else d
        
    metrics = {
        "severity": parse('SEVERITY', 5),
        "frequency": parse('FREQUENCY', 4)
    }
    return summary, metrics

def extract_red_flags(symptoms, details, model_type='local'):
    prompt = REDFLAGS_TEMPLATE.format(symptoms=symptoms, details=details)
    print(f"[LLM] extract_red_flags | Requested Model: {model_type}")
    
    if model_type == 'gemini':
        model = get_gemini()
        if model:
            try:
                print("[LLM] Calling Gemini API for red flags...")
                response = model.generate_content(prompt)
                result = response.text
                print("[LLM] Gemini SUCCESS.")
            except Exception as e:
                print(f"[LLM] Gemini API ERROR (red_flags): {e}")
                return extract_red_flags(symptoms, details, 'local')
        else:
            return extract_red_flags(symptoms, details, 'local')
    else:
        analyzer = get_analyzer()
        if not analyzer: return []
        print("[LLM] Processing with local LaMini model...")
        result = analyzer(prompt, max_length=128, do_sample=False)[0]['generated_text']
    
    flags = []
    
    if result and 'none' not in result.lower():
        for line in result.split('\n'):
            line = line.strip(' \n\t-.*')

            
            if 'SIGN -' in line.upper(): continue
            if '-' in line:
                parts = line.split('-', 1)
                name_clean = parts[0].strip()
                desc_clean = parts[1].strip() if len(parts) > 1 else "Detected"
                if name_clean.lower() not in ['sign', 'none']:
                    flags.append({"name": name_clean, "details": desc_clean})
            elif len(line) > 3 and 'none' not in line.lower() and 'sign' not in line.lower():
                flags.append({"name": line, "details": "Detected in analysis"})
    
    return flags

def extract_risks(symptoms, details, model_type='local'):
    prompt = RISKS_TEMPLATE.format(symptoms=symptoms, details=details)
    print(f"[LLM] extract_risks | Requested Model: {model_type}")
    
    if model_type == 'gemini':
        model = get_gemini()
        if model:
            try:
                print("[LLM] Calling Gemini API for risks...")
                response = model.generate_content(prompt)
                result = response.text
                print("[LLM] Gemini SUCCESS.")
            except Exception as e:
                print(f"[LLM] Gemini API ERROR (risks): {e}")
                return extract_risks(symptoms, details, 'local')
        else:
            return extract_risks(symptoms, details, 'local')
    else:
        analyzer = get_analyzer()
        if not analyzer: return []
        print("[LLM] Processing with local LaMini model...")
        result = analyzer(prompt, max_length=128, do_sample=False)[0]['generated_text']
    
    risks = []
    
    if result and 'none' not in result.lower():
        for line in result.split('\n'):
            line = line.strip(' \n\t-.*')
            if 'CONDITION -' in line.upper(): continue
            if '-' in line:
                parts = line.split('-', 1)
                name_clean = parts[0].strip()
                lvl_raw = parts[1].strip().capitalize() if len(parts) > 1 else "Medium"
                if name_clean.lower() not in ['condition', 'none']:
                    lvl_clean = lvl_raw if lvl_raw in ['Low', 'Medium', 'High'] else 'Medium'
                    risks.append({"name": name_clean, "level": lvl_clean})
            elif len(line) > 3 and 'none' not in line.lower() and 'condition' not in line.lower():
                risks.append({"name": line, "level": "Medium"})
                
    return risks

def extract_severity(symptoms, details, model_type='local'):
    prompt = SEVERITY_TEMPLATE.format(symptoms=symptoms, details=details)
    print(f"[LLM] extract_severity | Requested Model: {model_type}")
    
    if model_type == 'gemini':
        model = get_gemini()
        if model:
            try:
                print("[LLM] Calling Gemini API for severity...")
                response = model.generate_content(prompt)
                result = response.text
                print("[LLM] Gemini SUCCESS.")
            except Exception as e:
                print(f"[LLM] Gemini API ERROR (severity): {e}")
                return extract_severity(symptoms, details, 'local')
        else:
            return extract_severity(symptoms, details, 'local')
    else:
        analyzer = get_analyzer()
        if not analyzer: return 5
        print("[LLM] Processing with local LaMini model...")
        result = analyzer(prompt, max_length=128, do_sample=False)[0]['generated_text']
    
    nums = re.findall(r'\d+', result)
    if nums:
        val = int(nums[0])
        return min(max(val, 1), 10)
    return 5

def analyze_symptoms(symptoms, details, model_type='local'):
    print(f"\n[ORCHESTRATOR] Starting health analysis. Requested AI: {model_type}")
    try:
        summary, metrics = analyze_metrics(symptoms, details, model_type)
        red_flags = extract_red_flags(symptoms, details, model_type)
        risks = extract_risks(symptoms, details, model_type)
        
        # Dedicated severity call
        severity = extract_severity(symptoms, details, model_type)
        metrics['severity'] = severity
        
        return summary, "Consult medical professional.", metrics, red_flags, risks
    except Exception as e:
        print(f"[ORCHESTRATOR] FATAL ERROR: {e}")
        return "Analysis unavailable", "Error", {"severity": 0, "frequency": 0}, [], []
