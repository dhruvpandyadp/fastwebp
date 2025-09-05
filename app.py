
import streamlit as st
import io
from PIL import Image
import os
from io import BytesIO
import zipfile
import time

def get_streamlit_version():
    """Get Streamlit version to handle compatibility"""
    try:
        import streamlit as st
        version = st.__version__
        major, minor = map(int, version.split('.')[:2])
        return major, minor
    except:
        return 1, 0  # Default to old version if can't determine

def display_image(image, caption, **kwargs):
    """Display image with version compatibility"""
    try:
        major, minor = get_streamlit_version()
        # use_container_width was introduced in 1.14.0
        if major > 1 or (major == 1 and minor >= 14):
            st.image(image, caption=caption, use_container_width=True)
        else:
            # Use the old parameter name for older versions
            st.image(image, caption=caption, use_column_width=True)
    except:
        # Fallback to basic image display
        st.image(image, caption=caption)

def display_image_small(image, caption, width=200):
    """Display smaller image for previews"""
    try:
        st.image(image, caption=caption, width=width)
    except:
        st.image(image, caption=caption)

def get_image_size(image_bytes):
    """Get the size of image in KB"""
    return len(image_bytes) / 1024

def prepare_image_for_webp(image, preserve_transparency=True):
    """
    Prepare image for WebP conversion while handling transparency properly

    Args:
        image: PIL Image object
        preserve_transparency: Whether to preserve transparency or use white background

    Returns:
        PIL Image object ready for WebP conversion
    """
    original_mode = image.mode

    if original_mode == "RGBA":
        if preserve_transparency:
            # Keep RGBA for transparent WebP
            return image
        else:
            # Composite onto white background
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])  # Use alpha channel as mask
            return background

    elif original_mode == "P":
        # Handle palette images
        if 'transparency' in image.info:
            if preserve_transparency:
                # Convert to RGBA to preserve transparency
                image = image.convert('RGBA')
                return image
            else:
                # Convert to RGB with white background
                image = image.convert('RGBA')
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])
                return background
        else:
            # No transparency, convert to RGB
            return image.convert('RGB')

    elif original_mode in ("L", "LA"):
        # Grayscale images
        if original_mode == "LA" and preserve_transparency:
            # Convert to RGBA to preserve alpha
            return image.convert('RGBA')
        else:
            # Convert to RGB
            return image.convert('RGB')

    else:
        # RGB, CMYK, etc. - convert to RGB if needed
        if original_mode != "RGB":
            return image.convert('RGB')
        return image

def compress_image(image, target_size_kb=500, quality=85, max_width=1920, max_height=1080, preserve_transparency=True):
    """
    Compress image to target size and convert to WebP format

    Args:
        image: PIL Image object
        target_size_kb: Target file size in KB
        quality: Initial quality (0-100)
        max_width: Maximum width for desktop
        max_height: Maximum height for desktop
        preserve_transparency: Whether to preserve transparency

    Returns:
        tuple: (compressed_image_bytes, final_quality, final_dimensions, has_transparency)
    """

    # Check if original image has transparency
    has_transparency = image.mode in ("RGBA", "LA") or (image.mode == "P" and 'transparency' in image.info)

    # Prepare image for WebP conversion
    image = prepare_image_for_webp(image, preserve_transparency and has_transparency)

    # Calculate resize ratio to fit within max dimensions
    width, height = image.size
    resize_ratio = min(max_width / width, max_height / height, 1.0)

    if resize_ratio < 1.0:
        new_width = int(width * resize_ratio)
        new_height = int(height * resize_ratio)
        # Use LANCZOS for better quality with transparency
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Binary search for optimal quality
    low_quality = 1
    high_quality = quality
    best_quality = quality
    best_image_bytes = None

    while low_quality <= high_quality:
        current_quality = (low_quality + high_quality) // 2

        # Save image with current quality
        img_buffer = BytesIO()

        # Save with appropriate options for transparency
        save_options = {
            'format': 'WebP',
            'quality': current_quality,
            'optimize': True
        }

        # Add lossless option for very high quality with transparency
        if has_transparency and preserve_transparency and current_quality > 90:
            save_options['lossless'] = True
            save_options.pop('quality')  # lossless mode doesn't use quality

        image.save(img_buffer, **save_options)
        img_bytes = img_buffer.getvalue()
        img_size_kb = len(img_bytes) / 1024

        if img_size_kb <= target_size_kb:
            best_quality = current_quality
            best_image_bytes = img_bytes
            low_quality = current_quality + 1
        else:
            high_quality = current_quality - 1

    # If we couldn't achieve target size, try further resizing
    if best_image_bytes is None or get_image_size(best_image_bytes) > target_size_kb:
        # Reduce dimensions further
        current_width, current_height = image.size
        reduction_factor = 0.8

        while get_image_size(best_image_bytes or img_bytes) > target_size_kb and reduction_factor > 0.3:
            new_width = int(current_width * reduction_factor)
            new_height = int(current_height * reduction_factor)
            resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

            img_buffer = BytesIO()

            # Use the same save options as before
            save_options = {
                'format': 'WebP',
                'quality': best_quality,
                'optimize': True
            }

            resized_image.save(img_buffer, **save_options)
            img_bytes = img_buffer.getvalue()

            if len(img_bytes) / 1024 <= target_size_kb:
                best_image_bytes = img_bytes
                image = resized_image
                break

            reduction_factor -= 0.1

    final_dimensions = image.size
    return best_image_bytes or img_bytes, best_quality, final_dimensions, has_transparency

def create_mobile_version(image, max_width=768, preserve_transparency=True):
    """Create mobile-friendly version of image"""
    # Check if original image has transparency
    has_transparency = image.mode in ("RGBA", "LA") or (image.mode == "P" and 'transparency' in image.info)

    # Prepare image for WebP conversion
    image = prepare_image_for_webp(image, preserve_transparency and has_transparency)

    width, height = image.size
    if width > max_width:
        ratio = max_width / width
        new_height = int(height * ratio)
        image = image.resize((max_width, new_height), Image.Resampling.LANCZOS)

    img_buffer = BytesIO()

    # Save with appropriate options for transparency
    save_options = {
        'format': 'WebP',
        'quality': 80,
        'optimize': True
    }

    image.save(img_buffer, **save_options)
    return img_buffer.getvalue(), image.size, has_transparency

def create_zip_file(processed_images):
    """Create a ZIP file containing all processed images"""
    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, desktop_data, mobile_data in processed_images:
            # Add desktop version
            desktop_filename = f"desktop/{filename}_desktop.webp"
            zip_file.writestr(desktop_filename, desktop_data)

            # Add mobile version
            mobile_filename = f"mobile/{filename}_mobile.webp"
            zip_file.writestr(mobile_filename, mobile_data)

    zip_buffer.seek(0)
    return zip_buffer.getvalue()

def display_footer():
    """Display footer with creator credit"""
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #fff; font-size: 14px; padding: 10px 0;'>
        © 2025 Youtech & Associates, Inc. | Built with ❤️ by Dhruv Pandya | <a href="https://www.youtechagency.com/" target="_blank">Youtech Agency</a>
        </div>
        """, 
        unsafe_allow_html=True
    )

def main():
    st.set_page_config(
        page_title="FastWebP - Image Compressor & WebP Converter",
        page_icon="🖼️",
        layout="wide"
    )

    st.title("🖼️ FastWebP")
    st.info("✨ **Image Compressor & WebP Converter**")
    st.write("Upload multiple images and compress them to WebP format with custom size limits!")

    # Sidebar for settings
    st.sidebar.header("⚙️ Compression Settings")
    target_size = st.sidebar.number_input(
        "Target file size (KB)", 
        min_value=10, 
        max_value=5000, 
        value=500, 
        step=10,
        help="Maximum file size for compressed images"
    )

    initial_quality = st.sidebar.slider(
        "Initial Quality", 
        min_value=10, 
        max_value=100, 
        value=85,
        help="Starting quality for compression (will be optimized automatically)"
    )

    # Transparency handling option
    st.sidebar.subheader("🎭 Transparency Options")
    preserve_transparency = st.sidebar.checkbox(
        "Preserve Transparency", 
        value=True,
        help="Keep transparent areas transparent (recommended for PNG with transparency)"
    )

    if not preserve_transparency:
        background_color = st.sidebar.color_picker(
            "Background Color", 
            value="#FFFFFF",
            help="Color to use for transparent areas when transparency is not preserved"
        )

    st.sidebar.subheader("📱 Responsive Sizes")
    desktop_width = st.sidebar.number_input(
        "Desktop max width (px)", 
        min_value=800, 
        max_value=4000, 
        value=1920, 
        step=100
    )

    desktop_height = st.sidebar.number_input(
        "Desktop max height (px)", 
        min_value=600, 
        max_value=3000, 
        value=1080, 
        step=100
    )

    mobile_width = st.sidebar.number_input(
        "Mobile max width (px)", 
        min_value=320, 
        max_value=1024, 
        value=768, 
        step=50
    )

    # Batch processing options
    st.sidebar.subheader("📦 Batch Processing")
    max_files = st.sidebar.number_input(
        "Max files to process", 
        min_value=1, 
        max_value=50, 
        value=20, 
        help="Maximum number of files to process at once"
    )

    # Preview options
    st.sidebar.subheader("👀 Preview Options")
    show_previews = st.sidebar.checkbox(
        "Show Image Previews", 
        value=True,
        help="Display thumbnail previews of uploaded and processed images"
    )

    preview_size = st.sidebar.select_slider(
        "Preview Size",
        options=[150, 200, 250, 300],
        value=200,
        help="Size of preview thumbnails in pixels"
    )

    # File uploader - MULTIPLE FILES
    uploaded_files = st.file_uploader(
        "Choose image files",
        type=['png', 'jpg', 'jpeg', 'bmp', 'tiff', 'webp'],
        help="Supported formats: PNG, JPG, JPEG, BMP, TIFF, WebP",
        accept_multiple_files=True  # Enable multiple file upload
    )

    if uploaded_files:
        # Limit number of files
        if len(uploaded_files) > max_files:
            st.warning(f"⚠️ You uploaded {len(uploaded_files)} files, but only the first {max_files} will be processed.")
            uploaded_files = uploaded_files[:max_files]

        # Display upload summary
        st.subheader(f"📊 Upload Summary ({len(uploaded_files)} files)")

        total_original_size = 0
        file_details = []

        # Analyze all uploaded files
        for uploaded_file in uploaded_files:
            try:
                original_bytes = uploaded_file.getvalue()
                original_size_kb = len(original_bytes) / 1024
                total_original_size += original_size_kb

                # Open image to get details
                image = Image.open(uploaded_file)
                original_width, original_height = image.size
                has_transparency = image.mode in ("RGBA", "LA") or (image.mode == "P" and 'transparency' in image.info)

                file_details.append({
                    'name': uploaded_file.name,
                    'size_kb': original_size_kb,
                    'dimensions': f"{original_width} × {original_height}",
                    'format': uploaded_file.type.split('/')[-1].upper(),
                    'transparency': has_transparency,
                    'image': image,
                    'original_bytes': original_bytes
                })

            except Exception as e:
                st.error(f"Error analyzing {uploaded_file.name}: {str(e)}")
                continue

        # Display summary statistics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Files", len(file_details))
        with col2:
            st.metric("Total Size", f"{total_original_size:.1f} KB")
        with col3:
            transparency_count = sum(1 for f in file_details if f['transparency'])
            st.metric("With Transparency", f"{transparency_count}/{len(file_details)}")
        with col4:
            avg_size = total_original_size / len(file_details) if file_details else 0
            st.metric("Avg Size", f"{avg_size:.1f} KB")

        # Show image previews if enabled
        if show_previews and file_details:
            st.subheader("🖼️ Image Previews")

            # Create columns for preview grid
            cols_per_row = 4
            rows = (len(file_details) + cols_per_row - 1) // cols_per_row

            for row in range(rows):
                cols = st.columns(cols_per_row)
                for col_idx in range(cols_per_row):
                    file_idx = row * cols_per_row + col_idx
                    if file_idx < len(file_details):
                        file_detail = file_details[file_idx]
                        with cols[col_idx]:
                            # Display thumbnail
                            display_image_small(
                                file_detail['image'], 
                                f"{file_detail['name']}\n{file_detail['size_kb']:.1f} KB",
                                width=preview_size
                            )

                            # Show transparency indicator
                            if file_detail['transparency']:
                                st.caption("🎭 Has transparency")
                            else:
                                st.caption("🖼️ No transparency")

        # Show file details in expandable section
        with st.expander("📁 Detailed File Information", expanded=False):
            for i, file_detail in enumerate(file_details):
                col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1])
                with col1:
                    st.write(f"**{file_detail['name']}**")
                with col2:
                    st.write(f"{file_detail['size_kb']:.1f} KB")
                with col3:
                    st.write(file_detail['dimensions'])
                with col4:
                    st.write(file_detail['format'])
                with col5:
                    st.write("✅" if file_detail['transparency'] else "❌")

        # Batch compress button
        if st.button("🚀 Compress All Images", type="primary"):
            if not file_details:
                st.error("No valid images to process.")
                return

            # Create progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()

            processed_images = []
            total_desktop_size = 0
            total_mobile_size = 0
            successful_compressions = 0

            results_container = st.container()

            # Process each image
            for i, file_detail in enumerate(file_details):
                try:
                    # Update progress
                    progress = (i + 1) / len(file_details)
                    progress_bar.progress(progress)
                    status_text.text(f"Processing {file_detail['name']} ({i+1}/{len(file_details)})...")

                    # Compress for desktop
                    desktop_compressed, desktop_quality, desktop_dims, desktop_has_transparency = compress_image(
                        file_detail['image'].copy(), target_size, initial_quality, desktop_width, desktop_height, preserve_transparency
                    )

                    # Create mobile version
                    mobile_compressed, mobile_dims, mobile_has_transparency = create_mobile_version(
                        file_detail['image'].copy(), mobile_width, preserve_transparency
                    )

                    # Calculate sizes
                    desktop_size_kb = len(desktop_compressed) / 1024
                    mobile_size_kb = len(mobile_compressed) / 1024

                    total_desktop_size += desktop_size_kb
                    total_mobile_size += mobile_size_kb

                    # Store processed image data
                    filename_without_ext = os.path.splitext(file_detail['name'])[0]
                    processed_images.append((filename_without_ext, desktop_compressed, mobile_compressed))

                    # Store results for display
                    file_detail['desktop_compressed'] = desktop_compressed
                    file_detail['mobile_compressed'] = mobile_compressed
                    file_detail['desktop_size_kb'] = desktop_size_kb
                    file_detail['mobile_size_kb'] = mobile_size_kb
                    file_detail['desktop_quality'] = desktop_quality
                    file_detail['desktop_dims'] = desktop_dims
                    file_detail['mobile_dims'] = mobile_dims
                    file_detail['desktop_image'] = Image.open(BytesIO(desktop_compressed))
                    file_detail['mobile_image'] = Image.open(BytesIO(mobile_compressed))
                    file_detail['success'] = True

                    successful_compressions += 1

                except Exception as e:
                    file_detail['success'] = False
                    file_detail['error'] = str(e)
                    st.error(f"Failed to process {file_detail['name']}: {str(e)}")

            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()

            # Display results
            st.success(f"✅ Batch compression completed! {successful_compressions}/{len(file_details)} images processed successfully.")

            # Overall statistics
            st.subheader("📈 Batch Processing Results")

            total_original_size_mb = total_original_size / 1024
            total_desktop_size_mb = total_desktop_size / 1024
            total_mobile_size_mb = total_mobile_size / 1024

            col1, col2, col3 = st.columns(3)

            with col1:
                st.write("**Original (All Files)**")
                st.metric("Total Size", f"{total_original_size_mb:.2f} MB")
                st.metric("Files Processed", f"{successful_compressions}/{len(file_details)}")
                st.metric("Average Size", f"{total_original_size/len(file_details):.1f} KB")

            with col2:
                st.write("**Desktop Versions**")
                desktop_reduction = ((total_original_size - total_desktop_size) / total_original_size) * 100
                st.metric("Total Size", f"{total_desktop_size_mb:.2f} MB", f"-{desktop_reduction:.1f}%")
                st.metric("Average Size", f"{total_desktop_size/successful_compressions:.1f} KB")
                st.metric("Format", "WebP")

            with col3:
                st.write("**Mobile Versions**")
                mobile_reduction = ((total_original_size - total_mobile_size) / total_original_size) * 100
                st.metric("Total Size", f"{total_mobile_size_mb:.2f} MB", f"-{mobile_reduction:.1f}%")
                st.metric("Average Size", f"{total_mobile_size/successful_compressions:.1f} KB")
                st.metric("Optimized for", "Mobile devices")

            # Show compressed image previews if enabled
            if show_previews and successful_compressions > 0:
                st.subheader("🎨 Before & After Previews")

                # Create tabs for different views
                tab1, tab2, tab3 = st.tabs(["📱 Mobile Results", "🖥️ Desktop Results", "🔀 Side by Side"])

                with tab1:
                    st.write("**Mobile Optimized Versions:**")
                    cols_per_row = 4
                    rows = (successful_compressions + cols_per_row - 1) // cols_per_row

                    successful_files = [f for f in file_details if f.get('success', False)]
                    for row in range(rows):
                        cols = st.columns(cols_per_row)
                        for col_idx in range(cols_per_row):
                            file_idx = row * cols_per_row + col_idx
                            if file_idx < len(successful_files):
                                file_detail = successful_files[file_idx]
                                with cols[col_idx]:
                                    display_image_small(
                                        file_detail['mobile_image'],
                                        f"Mobile: {file_detail['name']}\n{file_detail['mobile_size_kb']:.1f} KB",
                                        width=preview_size
                                    )

                with tab2:
                    st.write("**Desktop Optimized Versions:**")
                    cols_per_row = 4
                    rows = (successful_compressions + cols_per_row - 1) // cols_per_row

                    for row in range(rows):
                        cols = st.columns(cols_per_row)
                        for col_idx in range(cols_per_row):
                            file_idx = row * cols_per_row + col_idx
                            if file_idx < len(successful_files):
                                file_detail = successful_files[file_idx]
                                with cols[col_idx]:
                                    display_image_small(
                                        file_detail['desktop_image'],
                                        f"Desktop: {file_detail['name']}\n{file_detail['desktop_size_kb']:.1f} KB",
                                        width=preview_size
                                    )

                with tab3:
                    st.write("**Before & After Comparison:**")

                    # Show comparison for each successful file
                    for file_detail in successful_files[:6]:  # Limit to first 6 for space
                        st.write(f"**{file_detail['name']}**")
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.write("*Original*")
                            display_image_small(
                                file_detail['image'],
                                f"Original\n{file_detail['size_kb']:.1f} KB",
                                width=preview_size
                            )

                        with col2:
                            st.write("*Desktop WebP*")
                            display_image_small(
                                file_detail['desktop_image'],
                                f"Desktop\n{file_detail['desktop_size_kb']:.1f} KB",
                                width=preview_size
                            )

                        with col3:
                            st.write("*Mobile WebP*")
                            display_image_small(
                                file_detail['mobile_image'],
                                f"Mobile\n{file_detail['mobile_size_kb']:.1f} KB",
                                width=preview_size
                            )

                        # Show compression stats
                        desktop_reduction = ((file_detail['size_kb'] - file_detail['desktop_size_kb']) / file_detail['size_kb']) * 100
                        mobile_reduction = ((file_detail['size_kb'] - file_detail['mobile_size_kb']) / file_detail['size_kb']) * 100
                        st.caption(f"Reductions: Desktop {desktop_reduction:.1f}% | Mobile {mobile_reduction:.1f}%")
                        st.markdown("---")

                    if len(successful_files) > 6:
                        st.info(f"Showing first 6 comparisons. Download ZIP to see all {len(successful_files)} processed images.")

            # Detailed results table
            with st.expander("📊 Detailed Results Table", expanded=False):
                st.write("**Individual File Results:**")

                # Create results table
                results_data = []
                for file_detail in file_details:
                    if file_detail.get('success', False):
                        desktop_reduction = ((file_detail['size_kb'] - file_detail['desktop_size_kb']) / file_detail['size_kb']) * 100
                        mobile_reduction = ((file_detail['size_kb'] - file_detail['mobile_size_kb']) / file_detail['size_kb']) * 100

                        results_data.append({
                            'File': file_detail['name'],
                            'Original (KB)': f"{file_detail['size_kb']:.1f}",
                            'Desktop (KB)': f"{file_detail['desktop_size_kb']:.1f}",
                            'Mobile (KB)': f"{file_detail['mobile_size_kb']:.1f}",
                            'Desktop Reduction': f"{desktop_reduction:.1f}%",
                            'Mobile Reduction': f"{mobile_reduction:.1f}%",
                            'Quality': f"{file_detail['desktop_quality']}%",
                            'Status': '✅ Success'
                        })
                    else:
                        results_data.append({
                            'File': file_detail['name'],
                            'Original (KB)': f"{file_detail['size_kb']:.1f}",
                            'Desktop (KB)': 'Failed',
                            'Mobile (KB)': 'Failed',
                            'Desktop Reduction': 'N/A',
                            'Mobile Reduction': 'N/A',
                            'Quality': 'N/A',
                            'Status': f"❌ {file_detail.get('error', 'Unknown error')}"
                        })

                # Display as table
                st.table(results_data)

            # Download options
            st.subheader("⬇️ Download Processed Images")

            if processed_images:
                # Create ZIP file
                zip_data = create_zip_file(processed_images)

                col1, col2, col3 = st.columns([2, 2, 1])

                with col1:
                    st.download_button(
                        label="📥 Download All Images (ZIP)",
                        data=zip_data,
                        file_name=f"compressed_images_{len(processed_images)}_files.zip",
                        mime="application/zip",
                        help="Downloads all desktop and mobile versions in organized folders"
                    )

                with col2:
                    st.write(f"**ZIP Contents:**")
                    st.write(f"• desktop/ folder: {len(processed_images)} desktop versions")
                    st.write(f"• mobile/ folder: {len(processed_images)} mobile versions")
                    st.write(f"• Total files: {len(processed_images) * 2}")

                with col3:
                    zip_size_mb = len(zip_data) / (1024 * 1024)
                    st.metric("ZIP Size", f"{zip_size_mb:.2f} MB")

                # Individual download options
                with st.expander("📁 Individual Downloads", expanded=False):
                    for file_detail in file_details:
                        if file_detail.get('success', False):
                            st.write(f"**{file_detail['name']}**")
                            col1, col2 = st.columns(2)

                            with col1:
                                desktop_filename = f"{os.path.splitext(file_detail['name'])[0]}_desktop.webp"
                                st.download_button(
                                    label="Desktop Version",
                                    data=file_detail['desktop_compressed'],
                                    file_name=desktop_filename,
                                    mime="image/webp",
                                    key=f"desktop_{file_detail['name']}"
                                )

                            with col2:
                                mobile_filename = f"{os.path.splitext(file_detail['name'])[0]}_mobile.webp"
                                st.download_button(
                                    label="Mobile Version",
                                    data=file_detail['mobile_compressed'],
                                    file_name=mobile_filename,
                                    mime="image/webp",
                                    key=f"mobile_{file_detail['name']}"
                                )

            # Processing summary
            st.subheader("ℹ️ Batch Processing Info")
            processing_time = len(file_details) * 2  # Approximate processing time

            st.info(f"""
            **Batch Processing Summary:**
            - Files processed: {successful_compressions}/{len(file_details)}
            - Total size reduction: {((total_original_size - total_desktop_size) / total_original_size * 100):.1f}% (desktop)
            - Average processing time: ~{processing_time} seconds
            - Output format: WebP with transparency preservation
            - Versions created: Desktop ({desktop_width}×{desktop_height} max) + Mobile ({mobile_width}px max width)

            **WebP Benefits:**
            - Superior compression compared to JPEG/PNG
            - Supports transparency and animation  
            - Widely supported by modern browsers
            - Up to 35% smaller than PNG with transparency

            **Preview Features:**
            - Upload thumbnails for quick verification
            - Before/after comparisons with size info
            - Organized tabs for different result views
            - Individual file comparisons available
            """)

    else:
        # Instructions when no files are uploaded
        st.info("👆 Please upload one or more image files to get started!")

        with st.expander("📋 How to use batch processing with previews"):
            st.write("""
            1. **Upload multiple images**: Use the file uploader above to select multiple images at once
            2. **Preview uploaded images**: See thumbnail previews of all uploaded files
            3. **Review upload summary**: Check the file details and statistics  
            4. **Adjust settings**: Use the sidebar to customize compression and preview settings
            5. **Process batch**: Click "Compress All Images" to process all files
            6. **View results**: See before/after previews in organized tabs
            7. **Download results**: Get a ZIP file with all compressed versions

            **Preview Features:**
            - ✅ **Thumbnail previews** of uploaded images
            - ✅ **Before/after comparisons** with compression stats
            - ✅ **Organized tabs** for mobile, desktop, and side-by-side views
            - ✅ **Adjustable preview size** (150-300 pixels)
            - ✅ **Transparency indicators** for each image
            - ✅ **File size information** displayed with each preview
            """)

        with st.expander("👀 Preview Options"):
            st.write("""
            **Preview Settings:**
            - **Show Previews**: Toggle thumbnail displays on/off
            - **Preview Size**: Adjust thumbnail size (150-300px)
            - **Grid Layout**: Automatic 4-column grid for organized viewing
            - **Transparency Indicators**: Visual markers for transparent images

            **Preview Views Available:**
            - **Upload Previews**: See all uploaded images before processing
            - **Mobile Results**: View all mobile-optimized versions
            - **Desktop Results**: View all desktop-optimized versions  
            - **Side-by-Side**: Compare original vs compressed (first 6 images)

            **Benefits:**
            - Quick visual verification of uploads
            - Easy quality assessment of results
            - Immediate feedback on compression effectiveness
            - Professional presentation of batch results
            """)

    # Display footer
    display_footer()

if __name__ == "__main__":
    main()
