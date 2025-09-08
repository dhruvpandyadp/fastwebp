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


def hide_streamlit_ui():
    """Hide Streamlit UI elements using CSS"""
    hide_streamlit_style = """
    <style>    
    /* Hide footer */
    footer {visibility: hidden;}
    
    /* Hide header */
    header {visibility: hidden;}
        
    /* Hide toolbar completely - comprehensive approach */
    div[data-testid="stToolbar"] {
        display: none !important;
    }
    
    /* Hide the decoration elements */
    div[data-testid="stDecoration"] {
        display: none !important;
    }
    
    /* Hide status widget */
    div[data-testid="stStatusWidget"] {
        visibility: hidden !important;
    }
    
    /* Hide GitHub icon and fork button */
    .css-1jc7ptx, .e1ewe7hr3, .viewerBadge_container__1QSob,
    .styles_viewerBadge__1yB5_, .viewerBadge_link__1S137,
    .viewerBadge_text__1JaDK {
        display: none !important;
    }
    
    /* Reduce top padding since we removed the header */
    .main .block-container {
        padding-top: 1rem;
    }
    </style>
    """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)

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

def create_zip_file(processed_images, include_mobile=True):
    """Create a ZIP file containing processed images"""
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, desktop_data, mobile_data in processed_images:
            # Always add desktop version
            desktop_filename = f"desktop/{filename}_desktop.webp"
            zip_file.writestr(desktop_filename, desktop_data)
            
            # Add mobile version only if requested
            if include_mobile and mobile_data:
                mobile_filename = f"mobile/{filename}_mobile.webp"
                zip_file.writestr(mobile_filename, mobile_data)
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()

def create_mobile_only_zip(processed_images):
    """Create a ZIP file containing only mobile versions"""
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, desktop_data, mobile_data in processed_images:
            if mobile_data:  # Only add if mobile version exists
                mobile_filename = f"{filename}_mobile.webp"
                zip_file.writestr(mobile_filename, mobile_data)
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()

def display_footer():
    """Display footer with creator credit"""
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666; padding: 20px;'>
        <p>© 2025 Youtech & Associates, Inc. | Built with ❤️ by Dhruv Pandya | <a href="https://www.youtechagency.com/" target="_blank">Youtech Agency</a>
       </p> </div>
        """,
        unsafe_allow_html=True
    )

def main():
    st.set_page_config(
        page_title="FastWebP - Image Compressor & WebP Converter",
        page_icon="🖼️",
        layout="wide"
    )
    
    # Hide Streamlit UI elements
    hide_streamlit_ui()

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

    # NEW: Mobile compression option
    st.sidebar.subheader("📱 Mobile Compression")
    enable_mobile = st.sidebar.checkbox(
        "Enable Mobile Version", 
        value=False,  # Default to desktop only
        help="Create mobile-optimized versions of images (smaller file sizes for mobile devices)"
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

    st.sidebar.subheader("🖥️ Desktop Sizes")
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

    # Mobile settings only shown when mobile is enabled
    if enable_mobile:
        st.sidebar.subheader("📱 Mobile Sizes")
        mobile_width = st.sidebar.number_input(
            "Mobile max width (px)", 
            min_value=320, 
            max_value=1024, 
            value=768, 
            step=50
        )
    else:
        mobile_width = 768  # Default value

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

        # Show compression mode info
        if enable_mobile:
            st.info("📱 **Mobile mode enabled** - Both desktop and mobile versions will be created")
        else:
            st.info("🖥️ **Desktop mode only** - Only desktop versions will be created")

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
                                f"{file_detail['name']}\n{file_detail['size_kb']:.1f} KB\n{file_detail['dimensions']}", 
                                width=preview_size
                            )
                            # Show transparency indicator
                            if file_detail['transparency']:
                                st.caption("🎭 Has Transparency")

        # BATCH PROCESSING BUTTON
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

                    mobile_compressed = None
                    mobile_dims = None
                    mobile_has_transparency = False
                    mobile_size_kb = 0

                    # Create mobile version only if enabled
                    if enable_mobile:
                        mobile_compressed, mobile_dims, mobile_has_transparency = create_mobile_version(
                            file_detail['image'].copy(), mobile_width, preserve_transparency
                        )
                        mobile_size_kb = len(mobile_compressed) / 1024
                        total_mobile_size += mobile_size_kb

                    # Calculate sizes
                    desktop_size_kb = len(desktop_compressed) / 1024
                    total_desktop_size += desktop_size_kb

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
                    if mobile_compressed:
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

            if enable_mobile:
                col1, col2, col3 = st.columns(3)
            else:
                col1, col2 = st.columns(2)

            with col1:
                st.write("**Original (All Files)**")
                st.metric("Total Size", f"{total_original_size_mb:.2f} MB")
                st.metric("Files Processed", f"{successful_compressions}/{len(file_details)}")
                st.metric("Average Size", f"{total_original_size/len(file_details):.1f} KB")

            with col2:
                st.write("**Desktop Versions**")
                desktop_reduction = ((total_original_size - total_desktop_size) / total_original_size) * 100 if total_original_size > 0 else 0
                st.metric("Total Size", f"{total_desktop_size_mb:.2f} MB", delta=f"-{desktop_reduction:.1f}%")
                st.metric("Average Size", f"{total_desktop_size/successful_compressions:.1f} KB" if successful_compressions > 0 else "0 KB")
                st.metric("Space Saved", f"{(total_original_size - total_desktop_size)/1024:.2f} MB")

            if enable_mobile:
                with col3:
                    st.write("**Mobile Versions**")
                    mobile_reduction = ((total_original_size - total_mobile_size) / total_original_size) * 100 if total_original_size > 0 else 0
                    st.metric("Total Size", f"{total_mobile_size_mb:.2f} MB", delta=f"-{mobile_reduction:.1f}%")
                    st.metric("Average Size", f"{total_mobile_size/successful_compressions:.1f} KB" if successful_compressions > 0 else "0 KB")
                    st.metric("Space Saved", f"{(total_original_size - total_mobile_size)/1024:.2f} MB")

            # DOWNLOAD BUTTONS
            st.subheader("📥 Download Results")
            
            # Batch Download Options
            st.write("**Batch Downloads:**")
            if enable_mobile:
                # When mobile is enabled, show three download options
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    # Desktop + Mobile ZIP
                    zip_data = create_zip_file(processed_images, include_mobile=True)
                    st.download_button(
                        label="📦 Download All (Desktop + Mobile)",
                        data=zip_data,
                        file_name=f"compressed_images_all_{int(time.time())}.zip",
                        mime="application/zip",
                        help="Download both desktop and mobile versions in separate folders"
                    )
                
                with col2:
                    # Desktop Only ZIP
                    desktop_zip_data = create_zip_file(processed_images, include_mobile=False)
                    st.download_button(
                        label="🖥️ Download Desktop Only",
                        data=desktop_zip_data,
                        file_name=f"compressed_images_desktop_{int(time.time())}.zip",
                        mime="application/zip",
                        help="Download only desktop versions"
                    )
                
                with col3:
                    # Mobile Only ZIP
                    mobile_zip_data = create_mobile_only_zip(processed_images)
                    st.download_button(
                        label="📱 Download Mobile Only",
                        data=mobile_zip_data,
                        file_name=f"compressed_images_mobile_{int(time.time())}.zip",
                        mime="application/zip",
                        help="Download only mobile versions"
                    )
            else:
                # When mobile is disabled, show only desktop download
                desktop_zip_data = create_zip_file(processed_images, include_mobile=False)
                st.download_button(
                    label="📦 Download Desktop Images",
                    data=desktop_zip_data,
                    file_name=f"compressed_images_desktop_{int(time.time())}.zip",
                    mime="application/zip",
                    help="Download compressed desktop versions"
                )

            # INDIVIDUAL DOWNLOAD SECTION
            st.write("**Individual Downloads:**")
            successful_files = [f for f in file_details if f.get('success', False)]
            
            if successful_files:
                # Show individual download options for each image
                for i, file_detail in enumerate(successful_files):
                    with st.expander(f"📷 {file_detail['name']} - Individual Downloads"):
                        filename_without_ext = os.path.splitext(file_detail['name'])[0]
                        
                        # Show compression stats
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Original Size", f"{file_detail['size_kb']:.1f} KB")
                            st.metric("Desktop Size", f"{file_detail['desktop_size_kb']:.1f} KB")
                            if enable_mobile and file_detail['mobile_compressed']:
                                st.metric("Mobile Size", f"{file_detail['mobile_size_kb']:.1f} KB")
                        
                        with col2:
                            desktop_reduction = ((file_detail['size_kb'] - file_detail['desktop_size_kb']) / file_detail['size_kb']) * 100
                            st.metric("Desktop Reduction", f"{desktop_reduction:.1f}%")
                            if enable_mobile and file_detail['mobile_compressed']:
                                mobile_reduction = ((file_detail['size_kb'] - file_detail['mobile_size_kb']) / file_detail['size_kb']) * 100
                                st.metric("Mobile Reduction", f"{mobile_reduction:.1f}%")
                        
                        # Individual download buttons
                        if enable_mobile and file_detail['mobile_compressed']:
                            col1, col2 = st.columns(2)
                            with col1:
                                st.download_button(
                                    label="⬇️ Download Desktop Version",
                                    data=file_detail['desktop_compressed'],
                                    file_name=f"{filename_without_ext}_desktop.webp",
                                    mime="image/webp",
                                    key=f"desktop_{i}_{int(time.time())}"
                                )
                            with col2:
                                st.download_button(
                                    label="⬇️ Download Mobile Version",
                                    data=file_detail['mobile_compressed'],
                                    file_name=f"{filename_without_ext}_mobile.webp",
                                    mime="image/webp",
                                    key=f"mobile_{i}_{int(time.time())}"
                                )
                        else:
                            st.download_button(
                                label="⬇️ Download Desktop Version",
                                data=file_detail['desktop_compressed'],
                                file_name=f"{filename_without_ext}_desktop.webp",
                                mime="image/webp",
                                key=f"desktop_{i}_{int(time.time())}"
                            )

            # RESULTS PREVIEW
            if show_previews:
                st.subheader("🖼️ Results Preview")

                # Create tabs for different views
                if enable_mobile:
                    tab1, tab2, tab3 = st.tabs(["🖥️ Desktop Results", "📱 Mobile Results", "🔄 Side-by-Side"])
                else:
                    tab1, tab3 = st.tabs(["🖥️ Desktop Results", "🔄 Side-by-Side"])

                # Desktop Results Tab
                with tab1:
                    st.write("**Desktop Compressed Images:**")
                    
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
                                        f"Desktop: {file_detail['name']}\n{file_detail['desktop_size_kb']:.1f} KB\n{file_detail['desktop_dims'][0]} × {file_detail['desktop_dims'][1]}\nQuality: {file_detail['desktop_quality']}",
                                        width=preview_size
                                    )

                # Mobile Results Tab (only if mobile enabled)
                if enable_mobile:
                    with tab2:
                        st.write("**Mobile Compressed Images:**")
                        
                        for row in range(rows):
                            cols = st.columns(cols_per_row)
                            for col_idx in range(cols_per_row):
                                file_idx = row * cols_per_row + col_idx
                                if file_idx < len(successful_files):
                                    file_detail = successful_files[file_idx]
                                    with cols[col_idx]:
                                        if 'mobile_image' in file_detail:
                                            display_image_small(
                                                file_detail['mobile_image'],
                                                f"Mobile: {file_detail['name']}\n{file_detail['mobile_size_kb']:.1f} KB\n{file_detail['mobile_dims'][0]} × {file_detail['mobile_dims'][1]}",
                                                width=preview_size
                                            )

                # Side-by-Side Comparison Tab
                with tab3:
                    st.write("**Before vs After Comparison (First 6 images):**")
                    
                    comparison_files = successful_files[:6]  # Limit to 6 for comparison
                    
                    for file_detail in comparison_files:
                        st.write(f"**{file_detail['name']}**")
                        
                        if enable_mobile:
                            col1, col2, col3 = st.columns(3)
                        else:
                            col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("*Original*")
                            display_image_small(
                                file_detail['image'],
                                f"Original: {file_detail['size_kb']:.1f} KB\n{file_detail['dimensions']}",
                                width=preview_size
                            )
                        
                        with col2:
                            st.write("*Desktop Compressed*")
                            display_image_small(
                                file_detail['desktop_image'],
                                f"Desktop: {file_detail['desktop_size_kb']:.1f} KB\n{file_detail['desktop_dims'][0]} × {file_detail['desktop_dims'][1]}\nReduction: {((file_detail['size_kb'] - file_detail['desktop_size_kb']) / file_detail['size_kb'] * 100):.1f}%",
                                width=preview_size
                            )
                        
                        if enable_mobile:
                            with col3:
                                st.write("*Mobile Compressed*")
                                if 'mobile_image' in file_detail:
                                    display_image_small(
                                        file_detail['mobile_image'],
                                        f"Mobile: {file_detail['mobile_size_kb']:.1f} KB\n{file_detail['mobile_dims'][0]} × {file_detail['mobile_dims'][1]}\nReduction: {((file_detail['size_kb'] - file_detail['mobile_size_kb']) / file_detail['size_kb'] * 100):.1f}%",
                                        width=preview_size
                                    )

    else:
        # Instructions when no files are uploaded
        st.subheader("📋 Instructions")
        
        st.markdown("""
        **How to use FastWebP:**
        
        1. **Upload images**: Use the file uploader above to select multiple image files
        2. **Configure settings**: Use the sidebar to adjust compression and preview settings
        3. **Choose compression mode**: 
           - **Desktop only** (default): Creates optimized versions for desktop/web use
           - **Mobile enabled**: Creates both desktop and mobile-optimized versions
        4. **Process images**: Click "Compress All Images" to process all uploaded files
        5. **Download results**: Choose from available download options based on your selected mode
        
        **Compression Modes:**
        - **🖥️ Desktop Mode**: Creates high-quality compressed images suitable for desktop viewing
        - **📱 Mobile Mode**: Additionally creates smaller, mobile-optimized versions for faster loading on mobile devices
        
        **Download Options:**
        - **Batch downloads**: Download all images at once in ZIP format
        - **Individual downloads**: Download each image separately with detailed compression stats
        """)

        with st.expander("🎯 Feature Highlights"):
            st.write("""
            **Key Features:**
            - ✅ **Batch processing** of multiple images
            - ✅ **WebP conversion** for optimal file sizes
            - ✅ **Transparency preservation** for PNG files
            - ✅ **Responsive sizing** for desktop and mobile
            - ✅ **Quality optimization** to meet target file sizes
            - ✅ **Before/after previews** with compression statistics
            - ✅ **Flexible download options** based on your needs
            - ✅ **Individual image downloads** with detailed stats
            
            **Supported Formats:**
            - Input: PNG, JPG, JPEG, BMP, TIFF, WebP
            - Output: WebP (optimized for web use)
            """)

        with st.expander("📖 How to Use Batch Processing"):
            st.write("""
            **Batch Processing Workflow:**
            1. **Select multiple files**: Upload 1-50 images at once
            2. **Review upload summary**: Check the file details and statistics  
            3. **Adjust settings**: Use the sidebar to customize compression and preview settings
            4. **Process batch**: Click "Compress All Images" to process all files
            5. **View results**: See before/after previews in organized tabs
            6. **Download results**: Choose from batch or individual download options

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
