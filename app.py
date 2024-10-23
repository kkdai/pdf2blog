import streamlit as st
from pdf2image import convert_from_bytes
from PIL import Image
from pypdf import PdfReader
import base64
import requests
import os
import io
import json

# OpenAI API Key from environment variable "openai_api_key"
api_key = os.getenv("openai_api_key")

pdf_file_text = []

if "page_number" not in st.session_state:
    st.session_state["page_number"] = 0

if "my_text_area" not in st.session_state:
    st.session_state["my_text_area"] = ""


def read_pdf_page(file, page_number):
    pdfReader = PdfReader(file)
    page = pdfReader.pages[page_number]
    return page.extract_text()


def on_text_area_change():
    # print("Text area changed:", st.session_state["page_number"],
    #   "text:", st.session_state["my_text_area"])
    pdf_file_text[st.session_state["page_number"] - 1] = st.session_state[
        "my_text_area"
    ]


def on_select_page_change():
    print("Select page changed:", st.session_state["page_number"])
    st.session_state["my_text_area"] = pdf_file_text[
        st.session_state["page_number"] - 1
    ]


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
                        "text": "試著用繁體中文來解釋這一張投影片的內容，你可以參考 {extra_text} 來讓你更加了解。",
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
    st.set_page_config(page_title="上傳公文幫你找出公文資訊", layout="wide")
    st.title("上傳投影片 PDF 翻譯加上解釋")

    # PDF file upload
    pdf_file = st.file_uploader("Upload a PDF file", type=["pdf"])
    print("PDF file text:", pdf_file_text)

    if pdf_file:
        print("PDF file uploaded:", pdf_file.name)
        # Create a selectbox to choose the page number
        pdfReader = PdfReader(pdf_file)
        print("Number of pages:", len(pdfReader.pages))
        page_numbers = list(range(1, len(pdfReader.pages) + 1))
        selected_page = st.selectbox("Select a page", page_numbers, key="page_number")
        selected_page -= 1

        # Read PDF text by page into list of strings
        for i in range(len(pdfReader.pages)):
            print("Reading page", i)
            pdf_file_text.append(read_pdf_page(pdf_file, i))

        # Convert the selected page to an image
        images = convert_from_bytes(pdf_file.getvalue())
        image = images[selected_page]

        # Create two columns to display the image and text
        img_col, openai_col = st.columns(2)

        # Display the image in the first column
        img_col.image(image, caption=f"Page {selected_page + 1}")
        display_text = pdf_file_text[selected_page]

        # Display the OpenAI response in the third column
        if st.button("GPT4-O Detect Image"):
            openai_response = openai_detect_image(image, display_text)
            result_str = extract_content_from_json(openai_response)
            openai_col.write(result_str)


if __name__ == "__main__":
    main()
