import sys 
import os


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import LLM
from Database import store_review
import Image_LLM

lang = "python"
code = '''
def add(a, b):
    return a + b
'''
img_path = "D:/Project/BACKEND/Test/image.png"

# review_result = LLM.code_review(code, lang)
# image_result = Image_LLM.img_code(img_path)
code_review = LLM.code_review(code, lang)

# print(review_result)
# print(image_result)
print(code_review)


# to_email = "kumaratul242005@gmail.com"

# from email_service import send_email
# token = "1234566"
# from email_service import send_email

# email_sent = send_email(to_email, token)

# if email_sent:
#     print(f"✅ Success! Modern email sent to {to_email}")
# else:
#     print("❌ Failed to send email. Check your API key and Sender Verification.")