import streamlit as st
import struct
import io
from PIL import Image
import texture2ddecoder

ASTC_MAGIC = 0x5CA1AB13

# তোমার আগের parse_astc ফাংশন
def parse_astc(raw_bytes):
    if len(raw_bytes) < 16:
        raise ValueError("ফাইলটি খুব ছোট, বৈধ .astc ফাইল নয়")
    magic = struct.unpack("<I", raw_bytes[0:4])[0]
    if magic != ASTC_MAGIC:
        raise ValueError("বৈধ .astc ফাইল নয় (magic header মিলছে না)")
    block_x, block_y = raw_bytes[4], raw_bytes[5]

    def read24(off):
        return raw_bytes[off] | (raw_bytes[off + 1] << 8) | (raw_bytes[off + 2] << 16)

    width, height = read24(7), read24(10)
    blocks_x = -(-width // block_x)
    blocks_y = -(-height // block_y)
    needed = blocks_x * blocks_y * 16
    payload = raw_bytes[16:16 + needed]
    
    return width, height, block_x, block_y, payload

# তোমার আগের decode ফাংশন
def decode_astc_to_image(raw_bytes):
    width, height, block_x, block_y, payload = parse_astc(raw_bytes)
    decoded = texture2ddecoder.decode_astc(payload, width, height, block_x, block_y)
    img = Image.frombytes("RGBA", (width, height), decoded, "raw", "BGRA")
    img = img.transpose(Image.FLIP_TOP_BOTTOM)
    return img

# ওয়েবসাইটের মূল ডিজাইন
st.set_page_config(page_title="ASTC Converter", layout="wide")
st.title("ASTC to PNG Converter")

# দুটি সেকশনের জন্য Tab তৈরি
tab1, tab2 = st.tabs(["📁 মাল্টিপল ফাইল কনভার্টার", "🔄 সিঙ্গেল ফাইল ও রিপ্লেস"])

# --- সেকশন ১: একসাথে অনেক ফাইল আপলোড ও গ্রিড ভিউ ---
with tab1:
    st.header("একাধিক ফাইল আপলোড করুন")
    uploaded_files = st.file_uploader("ASTC ফাইলগুলো সিলেক্ট করুন", accept_multiple_files=True, key="multi")
    
    if uploaded_files:
        # ২টা করে কলামের গ্রিড তৈরি (তোমার চাহিদামতো)
        cols = st.columns(2)
        
        for idx, file in enumerate(uploaded_files):
            col = cols[idx % 2] # ০ এবং ১ নম্বর কলামে পর্যায়ক্রমে বসবে
            with col:
                try:
                    img = decode_astc_to_image(file.getvalue())
                    st.image(img, caption=file.name, use_column_width=True)
                    
                    # ছবি ডাউনলোড করার জন্য বাটন
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    byte_im = buf.getvalue()
                    
                    st.download_button(
                        label=f"⬇️ ডাউনলোড {file.name}.png",
                        data=byte_im,
                        file_name=f"{file.name.split('.')[0]}.png",
                        mime="image/png"
                    )
                except Exception as e:
                    st.error(f"{file.name} প্রসেস করতে সমস্যা হয়েছে: {e}")
        st.markdown("---")

# --- সেকশন ২: সিঙ্গেল ফাইল দেখা এবং রিপ্লেস করা ---
with tab2:
    st.header("ফাইল দেখুন এবং নতুন ইমেজ দিয়ে রিপ্লেস করুন")
    single_file = st.file_uploader("একটি ASTC ফাইল আপলোড করুন", key="single")
    
    if single_file:
        try:
            original_img = decode_astc_to_image(single_file.getvalue())
            st.image(original_img, caption="আপনার আপলোড করা মূল ছবি", width=400)
            
            st.subheader("ছবি রিপ্লেস করুন")
            replacement_file = st.file_uploader("নতুন ছবি (PNG/JPG) আপলোড করুন", type=['png', 'jpg', 'jpeg'])
            
            if replacement_file:
                new_img = Image.open(replacement_file)
                st.image(new_img, caption="আপনার নতুন ছবি", width=400)
                
                # নতুন ছবি ডাউনলোড করার অপশন
                buf = io.BytesIO()
                new_img.save(buf, format="PNG")
                
                st.download_button(
                    label="⬇️ নতুন ছবিটি ডাউনলোড করুন",
                    data=buf.getvalue(),
                    file_name="replaced_image.png",
                    mime="image/png"
                )
        except Exception as e:
            st.error(f"সমস্যা হয়েছে: {e}")
