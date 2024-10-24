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
        max_tokens=1500,  # 增加 token 以獲取更詳細的描述
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
               - 可能遇到的挑戰和解決方案
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


def generate_blog_post(sections: list) -> dict:
    """
    將各個章節整合成完整的技術部落格文章
    """
    llm = ChatOpenAI(
        model_name="gpt-4o",
        temperature=0.3,
        max_tokens=7000,
        api_key=api_key,
    )

    # 將所有章節內容合併成一個字符串
    all_sections = "\n\n".join(sections)

    prompt_template = """
    請根據以下各個章節的內容，重新組織並撰寫一篇完整的技術部落格文章。

    要求：
    1. 使用台灣用語的繁體中文
    2. 文章結構需包含：
       - 文章標題（# 開頭）
       - 前言（## 開頭）：介紹本文主題和重要性
       - 技術背景（## 開頭）：說明相關技術背景和基本概念
       - 核心內容（根據提供的章節重新組織，使用 ## 或 ### 標題）
       - 實作建議（## 開頭）：提供實際應用的建議和最佳實踐
       - 未來展望（## 開頭）：討論技術的發展方向和潛在應用
       - 結論（## 開頭）：總結全文重點
    3. 內文要求：
       - 總字數至少 3000 字
       - 確保內容的連貫性和邏輯性
       - 適當引用原章節的技術細節
       - 加入自己的見解和分析
    4. 格式要求：
       - 使用 Markdown 格式
       - 適當使用粗體（**文字**）強調重要概念
       - 使用引用區塊（> 文字）標註重要說明
       - 使用項目符號整理重點
       - 必要時使用表格整理比較資訊
       - 保留原始程式碼區塊（如果有）

    以下是各章節內容：
    {text}

    請開始撰寫完整的部落格文章：
    """

    prompt = PromptTemplate.from_template(prompt_template)
    summarize_chain = load_summarize_chain(llm=llm, chain_type="stuff", prompt=prompt)
    document = Document(page_content=all_sections)
    summary = summarize_chain.invoke([document])

    return {"markdown": summary["output_text"], "rendered": summary["output_text"]}


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

            for i in range(total_pages):
                progress = (i + 1) / total_pages
                progress_bar.progress(progress)

                # 分析文字內容
                current_page_text = pdfReader.pages[i].extract_text()
                current_page_image = pdf_images[i]

                # 顯示圖片
                st.image(
                    current_page_image, caption=f"第 {i+1} 頁", use_column_width=True
                )

                # 分析圖片和文字內容
                openai_response = langchain_detect_image(
                    current_page_image, current_page_text, i + 1
                )
                result_str = extract_content_from_json(openai_response)

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

            # 產生完整部落格文章
            with st.spinner("正在整合內容，產生完整技術部落格文章..."):
                st.write("---")
                st.subheader("技術部落格文章")

                # 生成部落格文章
                blog_content = generate_blog_post(page_sections)

                # 顯示結果
                tab1, tab2, tab3 = st.tabs(["渲染結果", "Markdown 原始碼", "分頁內容"])

                with tab1:
                    st.markdown(blog_content["rendered"])

                with tab2:
                    st.text_area(
                        "Markdown 原始碼",
                        value=blog_content["markdown"],
                        height=500,
                        key="markdown_source",
                    )
                    if st.button("複製 Markdown 原始碼"):
                        st.write("Markdown 原始碼已複製到剪貼簿！")
                        st.text_area(
                            "",
                            value=blog_content["markdown"],
                            height=0,
                            key="hidden_copy_area",
                        )

                with tab3:
                    for i, section in enumerate(page_sections):
                        with st.expander(f"第 {i+1} 頁詳細內容"):
                            st.markdown(section)

        except Exception as e:
            st.error(f"處理 PDF 時發生錯誤: {str(e)}")


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


if __name__ == "__main__":
    main()
