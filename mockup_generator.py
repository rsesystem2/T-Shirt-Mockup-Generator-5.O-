import streamlit as st
from PIL import Image
import numpy as np
import zipfile
import io
import cv2
import os

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Mockup Studio", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 2rem;}
button {border-radius: 8px !important;}
</style>
""", unsafe_allow_html=True)

st.title("👕 Mockup Studio")
st.caption("Create clean product mockups in seconds")

# ---------------- SIDEBAR ----------------
st.sidebar.header("⚙️ Design Controls")

st.sidebar.markdown("### 🧵 Plain T-Shirts")
plain_padding = st.sidebar.slider("Print Size (Plain)", 0.2, 1.2, 0.45)
plain_offset = st.sidebar.slider("Vertical Position (Plain)", -50, 100, 23)

st.sidebar.markdown("### 🧍 Model T-Shirts")
model_padding = st.sidebar.slider("Print Size (Model)", 0.2, 1.2, 0.45)
model_offset = st.sidebar.slider("Vertical Position (Model)", -50, 100, 38)

st.sidebar.markdown("### 🎛️ Fine Adjustments")
x_shift = st.sidebar.slider("Horizontal Adjust", -200, 200, 0)
y_shift = st.sidebar.slider("Vertical Adjust", -200, 200, 0)
scale_override = st.sidebar.slider("Scale Multiplier", 0.5, 1.5, 1.0)

st.sidebar.markdown("### 🔁 Variations")
variation_count = st.sidebar.slider("Variations per Design", 1, 5, 2)

# ---------------- CACHE ----------------
@st.cache_data
def load_image(file):
    return Image.open(io.BytesIO(file.read())).convert("RGBA")

@st.cache_data
def get_bbox(image):
    img_cv = np.array(image.convert("RGB"))[:, :, ::-1]
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        11, 2
    )

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        return cv2.boundingRect(max(contours, key=cv2.contourArea))
    return None

# ---------------- UPLOAD ----------------
st.markdown("## 📤 Upload Files")

col1, col2 = st.columns(2)

with col1:
    design_files = st.file_uploader("Upload Designs", accept_multiple_files=True)

with col2:
    shirt_files = st.file_uploader("Upload T-Shirt Templates", accept_multiple_files=True)

# ---------------- DESIGN NAMING ----------------
design_names = {}
if design_files:
    st.markdown("## ✏️ Name Your Designs")
    for f in design_files:
        name = os.path.splitext(f.name)[0]
        design_names[f.name] = st.text_input(f.name, value=name)

# ---------------- PREVIEW ----------------
if design_files and shirt_files:
    st.markdown("## 👀 Live Preview")

    selected_design = st.selectbox("Choose Design", design_files, format_func=lambda x: x.name)
    selected_shirt = st.selectbox("Choose Template", shirt_files, format_func=lambda x: x.name)

    design = load_image(selected_design)
    shirt = load_image(selected_shirt)

    parts = selected_shirt.name.lower().split("_")
    is_model = "model" in parts

    padding = model_padding if is_model else plain_padding
    offset = model_offset if is_model else plain_offset

    bbox = get_bbox(shirt)

    if bbox:
        sx, sy, sw, sh = bbox

        scale = min(sw / design.width, sh / design.height)
        scale *= padding * scale_override

        new_w = int(design.width * scale)
        new_h = int(design.height * scale)

        resized = design.resize((new_w, new_h))

        x = sx + (sw - new_w) // 2 + x_shift
        y = sy + int(sh * offset / 100) + y_shift
    else:
        resized = design
        x = (shirt.width - design.width) // 2
        y = (shirt.height - design.height) // 2

    preview = shirt.copy()
    preview.paste(resized, (x, y), resized)

    st.image(preview, use_container_width=True)

# ---------------- GENERATE ----------------
if st.button("🚀 Generate Mockups"):
    if not (design_files and shirt_files):
        st.warning("Upload designs and templates first")
    else:
        progress = st.progress(0)

        master_zip = io.BytesIO()

        with zipfile.ZipFile(master_zip, "w", zipfile.ZIP_DEFLATED) as master:

            total = len(design_files)

            for i, d_file in enumerate(design_files):
                design = load_image(d_file)
                name = design_names.get(d_file.name, "design")

                for shirt_file in shirt_files:
                    shirt = load_image(shirt_file)

                    parts = shirt_file.name.lower().split("_")
                    is_model = "model" in parts
                    color = parts[0]

                    padding = model_padding if is_model else plain_padding
                    offset = model_offset if is_model else plain_offset

                    bbox = get_bbox(shirt)

                    for v in range(variation_count):
                        shirt_copy = shirt.copy()

                        if bbox:
                            sx, sy, sw, sh = bbox

                            scale = min(sw / design.width, sh / design.height)
                            scale *= padding * scale_override
                            scale *= (1 + v * 0.05)

                            new_w = int(design.width * scale)
                            new_h = int(design.height * scale)

                            resized = design.resize((new_w, new_h))

                            x = sx + (sw - new_w) // 2 + x_shift
                            y = sy + int(sh * offset / 100) + y_shift + v * 5
                        else:
                            resized = design
                            x = (shirt.width - design.width) // 2
                            y = (shirt.height - design.height) // 2

                        shirt_copy.paste(resized, (x, y), resized)

                        rgb = shirt_copy.convert("RGB")

                        img_bytes = io.BytesIO()
                        rgb.save(img_bytes, format="JPEG", quality=90, optimize=True)
                        img_bytes.seek(0)

                        filename = f"{name}_{color}_{'model' if is_model else 'plain'}_v{v+1}.jpg"
                        master.writestr(filename, img_bytes.read())

                progress.progress((i + 1) / total)

        master_zip.seek(0)

        st.download_button(
            "📦 Download All Mockups",
            data=master_zip,
            file_name="mockups_bundle.zip",
            mime="application/zip"
        )
