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


def generate_blog_post(text: str) -> dict:
    """
    Generate a detailed technical blog post in Markdown format.
    Returns both markdown and the rendered content.
    """
    llm = ChatOpenAI(
        model_name="gpt-4o",
        temperature=0.7,
        max_tokens=4000,  # 增加 token 限制以產生更長的內容
        api_key=api_key,
    )

    prompt_template = """
    請根據以下的投影片內容，撰寫一篇詳細的技術部落格文章。文章需要符合以下要求：

    1. 使用台灣用語的繁體中文
    2. 文章結構需包含（但不限於）：
       - 標題（# 開頭）
       - 前言（## 開頭）
       - 背景說明（## 開頭）
       - 技術原理（## 開頭）
       - 實作細節（## 開頭）
       - 效能分析（## 開頭）
       - 未來展望（## 開頭）
       - 結論（## 開頭）
    3. 內文至少 2000 字
    4. 使用 Markdown 格式撰寫，包含：
       - 適當的標題層級（#, ##, ###）
       - 重點使用粗體（**文字**）
       - 程式碼區塊使用 ```
       - 適當的換行和段落分隔
       - 重要概念使用引用區塊（> 文字）
       - 適當的項目符號（- 或 1.）
    5. 確保內容專業且具有技術深度
    6. 加入實用的程式碼範例（如果適用）
    7. 使用表格整理比較資訊（如果適用）

    以下是投影片內容：
    {text}

    請開始撰寫部落格文章：
    """

    prompt = PromptTemplate.from_template(prompt_template)
    summarize_chain = load_summarize_chain(llm=llm, chain_type="stuff", prompt=prompt)
    document = Document(page_content=text)
    summary = summarize_chain.invoke([document])

    return {"markdown": summary["output_text"], "rendered": summary["output_text"]}


def langchain_detect_image(image: Image.Image, extra_text: str = "") -> dict:
    """
    使用 ChatOpenAI 來分析圖片內容並生成技術部落格文章
    """
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    base64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")

    chat = ChatOpenAI(
        model="gpt-4o",
        max_tokens=1000,
        api_key=api_key,
    )

    message_content = [
        {
            "type": "text",
            "text": f"""
            請根據這張投影片圖片撰寫詳細的技術說明，需要：
            1. 清楚說明圖片中的技術概念
            2. 解釋圖片中的重要術語
            3. 分析圖片中展示的技術優勢
            4. 討論可能的應用場景
            5. 提供技術實作建議
            
            你可以參考以下文字來協助理解：
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
            "choices": [{"message": {"content": "圖片處理失敗", "role": "assistant"}}]
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

            for i in range(total_pages):
                progress = (i + 1) / total_pages
                progress_bar.progress(progress)

                st.write(f"處理第 {i+1} 頁...")

                current_page_text = pdfReader.pages[i].extract_text()
                with st.expander(f"第 {i+1} 頁文字內容"):
                    st.write(current_page_text)

                current_page_image = pdf_images[i]
                st.image(
                    current_page_image, caption=f"第 {i+1} 頁", use_column_width=True
                )

                with st.spinner(f"分析第 {i+1} 頁圖片中..."):
                    openai_response = langchain_detect_image(
                        current_page_image, current_page_text
                    )
                    result_str = extract_content_from_json(openai_response)
                    with st.expander(f"第 {i+1} 頁分析結果"):
                        st.write(result_str)

                pdf_file_text.append(result_str)

            progress_bar.progress(1.0)

            with st.spinner("產生技術部落格文章中..."):
                st.write("---")
                st.subheader("技術部落格文章")

                # 生成部落格文章
                blog_content = generate_blog_post("".join(pdf_file_text))

                # 創建兩個分頁來顯示 Markdown 原始碼和渲染後的結果
                tab1, tab2 = st.tabs(["渲染結果", "Markdown 原始碼"])

                with tab1:
                    st.markdown(blog_content["rendered"])

                with tab2:
                    st.text_area(
                        "Markdown 原始碼",
                        value=blog_content["markdown"],
                        height=500,
                        key="markdown_source",
                    )

                    # 添加複製按鈕
                    if st.button("複製 Markdown 原始碼"):
                        st.write("Markdown 原始碼已複製到剪貼簿！")
                        st.text_area(
                            "",
                            value=blog_content["markdown"],
                            height=0,
                            key="hidden_copy_area",
                        )

        except Exception as e:
            st.error(f"處理 PDF 時發生錯誤: {str(e)}")


if __name__ == "__main__":
    main()
