import streamlit as st
from pdf2image import convert_from_bytes
from pypdf import PdfReader
import base64
import os
import io
from langchain.chains.summarize import load_summarize_chain
from langchain_core.prompts import PromptTemplate
from langchain.docstore.document import Document
from langchain_openai import ChatOpenAI
from langchain.schema.messages import HumanMessage
from PIL import Image

# OpenAI API Key from environment variable
api_key = os.getenv("openai_api_key")
pdf_file_text = []


def save_image(image: Image.Image, page_num: int) -> str:
    """
    保存圖片並返回檔案路徑
    """
    if not os.path.exists("temp_images"):
        os.makedirs("temp_images")

    image_path = f"temp_images/page_{page_num}.jpg"
    image.save(image_path)
    return image_path


def generate_intro_and_future(content: str) -> dict:
    """
    基於內容生成前言和未來展望
    """
    llm = ChatOpenAI(
        model_name="gpt-4o",
        temperature=0.3,
        max_tokens=2000,
        api_key=api_key,
    )

    prompt_template = """
    請根據以下技術內容，分別生成兩個章節：前言和未來展望。
    將結果分成兩個部分回傳，以 [前言] 和 [未來展望] 標記開始。

    要求：
    1. 前言（## 開頭）：
       - 介紹本文主題和重要性
       - 說明文章要解決的問題
       - 簡述主要內容架構
    2. 未來展望（## 開頭）：
       - 討論技術的發展方向
       - 提出可能的應用場景
       - 預測未來趨勢
    3. 使用台灣用語的繁體中文
    4. 使用 Markdown 格式
    5. 每個章節至少 300 字

    內容：
    {text}

    請以下列格式回傳：
    [前言]
    (前言內容...)

    [未來展望]
    (未來展望內容...)
    """

    prompt = PromptTemplate.from_template(prompt_template)
    summarize_chain = load_summarize_chain(llm=llm, chain_type="stuff", prompt=prompt)
    document = Document(page_content=content)
    result = summarize_chain.invoke([document])

    # 分割前言和未來展望
    sections = result["output_text"].split("[未來展望]")
    intro = sections[0].replace("[前言]", "").strip()
    future = sections[1].strip() if len(sections) > 1 else ""

    return {"intro": intro, "future": future}


def langchain_detect_image(
    image: Image.Image, extra_text: str = "", page_num: int = 1
) -> dict:
    """
    使用 ChatOpenAI 來分析圖片內容並生成技術部落格文章的段落
    """
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    base64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")

    chat = ChatOpenAI(
        model="gpt-4o",
        temperature=0.3,
        max_tokens=1500,
        api_key=api_key,
    )

    message_content = [
        {
            "type": "text",
            "text": f"""
            請以技術部落格的一個章節的方式，詳細描述這張投影片的內容。需要：

            1. 提供一個適合的章節標題（使用 ### 開頭）
            2. 詳細解釋這張投影片想表達的核心概念
            3. 分析並說明：
               - 投影片中提到的技術重點
               - 重要的術語解釋
               - 技術原理說明
               - 實際應用場景
            4. 如果投影片中有程式碼，請解釋程式碼的功能和重點
            5. 如果有圖表，請詳細解釋圖表的含義
            6. 使用台灣用語的繁體中文撰寫
            7. 使用 Markdown 格式
            8. 確保這個章節的內容至少 300 字

            參考文字內容：
            {extra_text}
            """,
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
        },
    ]

    message = HumanMessage(content=message_content)

    try:
        response = chat.invoke([message])
        result = {
            "choices": [{"message": {"content": response.content, "role": "assistant"}}]
        }
        return result
    except Exception as e:
        st.error(f"處理圖片時發生錯誤: {str(e)}")
        return {
            "choices": [
                {
                    "message": {
                        "content": f"第 {page_num} 頁圖片處理失敗",
                        "role": "assistant",
                    }
                }
            ]
        }


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

    if not api_key:
        st.error("請設定 openai_api_key 環境變數")
        return

    pdf_file = st.file_uploader("上傳 PDF 檔案", type=["pdf"])

    if pdf_file:
        try:
            st.write(f"已上傳檔案：{pdf_file.name}")

            pdfReader = PdfReader(pdf_file)
            pdf_images = convert_from_bytes(pdf_file.getvalue())

            progress_bar = st.progress(0)
            total_pages = len(pdfReader.pages)

            # 用於存儲每頁的詳細分析
            page_sections = []
            image_paths = []

            for i in range(total_pages):
                progress = (i + 1) / total_pages
                progress_bar.progress(progress)

                # 分析文字內容
                current_page_text = pdfReader.pages[i].extract_text()
                current_page_image = pdf_images[i]

                # 保存圖片
                image_path = save_image(current_page_image, i + 1)
                image_paths.append(image_path)

                # 顯示圖片（30% 寬度）
                col1, col2, col3 = st.columns([3, 4, 3])
                with col2:
                    st.image(current_page_image, caption=f"第 {i+1} 頁")

                # 分析圖片和文字內容
                openai_response = langchain_detect_image(
                    current_page_image, current_page_text, i + 1
                )
                result_str = extract_content_from_json(openai_response)

                # 在每個章節後添加圖片引用
                result_str += f"\n\n![第 {i+1} 頁]({image_path})\n\n---\n"

                # 儲存這一頁的分析結果
                page_sections.append(result_str)

                # 顯示分析結果
                with st.expander(f"第 {i+1} 頁分析內容", expanded=False):
                    tab1, tab2 = st.tabs(["原始內容", "分析結果"])
                    with tab1:
                        st.write(current_page_text)
                    with tab2:
                        st.markdown(result_str)

            progress_bar.progress(1.0)

            # 生成完整部落格文章
            with st.spinner("正在整合內容，產生完整技術部落格文章..."):
                st.write("---")
                st.subheader("技術部落格文章")

                # 合併所有內容
                full_content = "\n\n".join(page_sections)

                # 生成前言和未來展望
                intro_and_future = generate_intro_and_future(full_content)

                # 組合最終文章（未來展望放在最後）
                final_blog_content = f"""
{intro_and_future['intro']}

## 技術內容

{full_content}

{intro_and_future['future']}
"""

                # 顯示結果
                tab1, tab2 = st.tabs(["渲染結果", "Markdown 原始碼"])

                with tab1:
                    st.markdown(final_blog_content)

                with tab2:
                    st.text_area(
                        "Markdown 原始碼",
                        value=final_blog_content,
                        height=500,
                        key="markdown_source",
                    )
                    if st.button("複製 Markdown 原始碼"):
                        st.write("Markdown 原始碼已複製到剪貼簿！")
                        st.text_area(
                            "",
                            value=final_blog_content,
                            height=0,
                            key="hidden_copy_area",
                        )

        except Exception as e:
            st.error(f"處理 PDF 時發生錯誤: {str(e)}")
            st.error(f"錯誤詳情: {str(e)}")
            import traceback

            st.error(f"堆疊追蹤: {traceback.format_exc()}")


if __name__ == "__main__":
    main()
