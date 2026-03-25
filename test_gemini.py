import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def test_gemini():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not found.")
        return

    print("Configuring Gemini...")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-flash-latest')
    
    print("Testing generation...")
    try:
        response = model.generate_content("Provide a one sentence medical summary for: headache and dizziness.")
        print(f"Response: {response.text}")
        print("SUCCESS: Gemini integration is working.")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    test_gemini()
