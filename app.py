import streamlit as st
from pdf2image import convert_from_bytes
from PIL import Image
from pypdf import PdfReader
import base64
import requests
import os
import io
import json
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.summarize import load_summarize_chain
from langchain.chains import LLMChain
from langchain_openai import OpenAI
from langchain_core.prompts import PromptTemplate
from langchain.docstore.document import Document
from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate
from langchain_openai import OpenAI
from PIL import Image
import io
import base64
from langchain_openai import ChatOpenAI
from langchain.schema.messages import HumanMessage
import io
import base64
from PIL import Image
from typing import Optional

# OpenAI API Key from environment variable "openai_api_key"
api_key = os.getenv("openai_api_key")
pdf_file_text = []


def summarize_text(text: str, max_tokens: int = 100) -> str:
    """
    Summarize a text using the Google Generative AI model.
    """
    llm = OpenAI(model_name="gpt-4o", temperature=0.5)

    prompt_template = """
    你需要根據這個投影片的文字來撰寫技術部落格，試著用台灣用語的繁體中文來解釋這份投影片的內容。
    需要有以下相關章節：
    - 前言
    - 痛點與以往做法
    - 解決方案
    - 結論與未來發展

    原文： "{text}"
    """

    prompt = PromptTemplate.from_template(prompt_template)

    summarize_chain = load_summarize_chain(llm=llm, chain_type="stuff", prompt=prompt)
    document = Document(page_content=text)
    summary = summarize_chain.invoke([document])
    return summary["output_text"]


def langchain_detect_image(image: Image.Image, extra_text: str = "") -> dict:
    """
    使用 Langchain 的 ChatOpenAI 來分析圖片內容並生成技術部落格文章

    Args:
        image (PIL.Image.Image): 要分析的圖片
        api_key (str): OpenAI API 金鑰
        extra_text (str, optional): 額外的參考文字. Defaults to "".

    Returns:
        dict: OpenAI 的回應內容
    """
    # 將 PIL Image 轉換成 base64
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    base64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")

    # 設定 ChatOpenAI
    chat = ChatOpenAI(
        model="gpt-4o",  # 使用支援視覺的模型
        max_tokens=1000,
        api_key=api_key,
    )

    # 準備訊息內容
    message_content = [
        {
            "type": "text",
            "text": f"你需要根據這張圖片撰寫技術部落格，試著用台灣用語的繁體中文來解釋這一張投影片的內容，你可以參考 {extra_text} 來讓你更加了解。",
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
        },
    ]

    # 建立 HumanMessage 物件
    message = HumanMessage(content=message_content)

    # 發送請求並獲取回應
    response = chat.invoke([message])

    # 將回應轉換為字典格式
    result = {
        "choices": [{"message": {"content": response.content, "role": "assistant"}}]
    }

    return result


def openai_detect_image(image, extra_text=""):
    # convert PIL Image to base64
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    base64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "你需要根據這張圖片撰寫技術部落格，試著用台灣用語的繁體中文來解釋這一張投影片的內容，你可以參考 {extra_text} 來讓你更加了解。",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            }
        ],
        "max_tokens": 1000,
    }

    response = requests.post(
        "https://api.openai.com/v1/chat/completions", headers=headers, json=payload
    )

    print(response.json())
    return response.json()


def extract_content_from_json(json_obj):
    """
    Extracts content from the 'choices' list in the given JSON object.

    Parameters:
    json_obj (dict): JSON object

    Returns:
    str: Extracted content, or an appropriate message if the object is empty or choices list is empty.
    """
    # No need to parse json_str, as json_obj is already a dictionary
    if json_obj:
        choices = json_obj.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            return content
        else:
            return "choices 列表为空"
    else:
        return "JSON 对象为空"


def main():
    st.set_page_config(page_title="上傳投影片 PDF 幫你寫成部落格", layout="wide")
    st.title("上傳投影片 PDF 幫你寫成中文部落格")

    # PDF file upload
    pdf_file = st.file_uploader("Upload a PDF file", type=["pdf"])
    print("PDF file text:", pdf_file_text)

    if pdf_file:
        print("PDF file uploaded:", pdf_file.name)
        # Create a selectbox to choose the page number
        pdfReader = PdfReader(pdf_file)
        print("Number of pages:", len(pdfReader.pages))

        # Convert the selected page to an image
        pdf_images = convert_from_bytes(pdf_file.getvalue())

        # Read PDF text by page into list of strings
        for i in range(len(pdfReader.pages)):
            st.write(f"Processing page: {i}...")

            # Extract the text from the current page
            current_page_text = pdfReader.pages[i].extract_text()
            st.write(f"Current_page_text: {current_page_text}...")

            # Extract the image from the current page
            current_page_image = pdf_images[i]
            st.image(current_page_image, caption=f"Page {i}")

            # Get image detail from the current page

            openai_response = langchain_detect_image(
                current_page_image, current_page_text
            )
            result_str = extract_content_from_json(openai_response)
            st.write(f"current_detail: {result_str}...")

            # Extract the content from the JSON response
            pdf_file_text.append(result_str)

        # Starting to summerzie final blog content
        st.write("Starting to summarize the final blog content...")
        blog_content = summarize_text("".join(pdf_file_text))
        st.write(f"Blog content: {blog_content}")


if __name__ == "__main__":
    main()
