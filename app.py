import streamlit as st
from pdf2image import convert_from_bytes
from pypdf import PdfReader
import base64
import os
import io
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.summarize import load_summarize_chain
from langchain_core.prompts import PromptTemplate
from langchain.docstore.document import Document
from langchain_openai import ChatOpenAI
from langchain.schema.messages import HumanMessage
from PIL import Image

# OpenAI API Key from environment variable
api_key = os.getenv("openai_api_key")
pdf_file_text = []


def summarize_text(text: str, max_tokens: int = 100) -> str:
    """
    Summarize text using ChatOpenAI model.
    """
    # 使用 ChatOpenAI 而不是 OpenAI
    llm = ChatOpenAI(
        model_name="gpt-4-turbo-preview",  # 使用正確的模型名稱
        temperature=0.5,
        api_key=api_key,
    )

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
    使用 ChatOpenAI 來分析圖片內容並生成技術部落格文章
    """
    # 將 PIL Image 轉換成 base64
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    base64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")

    # 設定 ChatOpenAI，使用正確的模型名稱
    chat = ChatOpenAI(
        model="gpt-4o",  # 使用支援視覺的正確模型名稱
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


def extract_content_from_json(json_obj):
    """
    從 JSON 物件中提取內容
    """
    if json_obj:
        choices = json_obj.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            return content
        return "choices 列表為空"
    return "JSON 物件為空"


def main():
    st.set_page_config(page_title="上傳投影片 PDF 幫你寫成部落格", layout="wide")
    st.title("上傳投影片 PDF 幫你寫成中文部落格")

    # PDF 檔案上傳
    pdf_file = st.file_uploader("上傳 PDF 檔案", type=["pdf"])

    if pdf_file:
        st.write(f"已上傳檔案：{pdf_file.name}")

        # 讀取 PDF
        pdfReader = PdfReader(pdf_file)
        pdf_images = convert_from_bytes(pdf_file.getvalue())

        # 處理每一頁
        for i in range(len(pdfReader.pages)):
            st.write(f"處理第 {i+1} 頁...")

            # 提取文字
            current_page_text = pdfReader.pages[i].extract_text()
            st.write(f"頁面文字：{current_page_text}")

            # 提取圖片
            current_page_image = pdf_images[i]
            st.image(current_page_image, caption=f"第 {i+1} 頁")

            # 分析圖片
            openai_response = langchain_detect_image(
                current_page_image, current_page_text
            )
            result_str = extract_content_from_json(openai_response)
            st.write(f"圖片分析結果：{result_str}")

            pdf_file_text.append(result_str)

        # 產生最終部落格內容
        st.write("開始產生最終部落格內容...")
        blog_content = summarize_text("".join(pdf_file_text))
        st.write(f"部落格內容：{blog_content}")


if __name__ == "__main__":
    main()
