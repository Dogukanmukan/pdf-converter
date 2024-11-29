import os
from pdf2image import convert_from_path
from PIL import Image
import img2pdf
import uuid
from datetime import datetime

class ConversionError(Exception):
    pass

def create_temp_directory():
    """Create a temporary directory for file processing"""
    temp_dir = os.path.join('uploads', str(uuid.uuid4()))
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir

def cleanup_temp_files(temp_dir):
    """Clean up temporary files after conversion"""
    try:
        for file in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, file))
        os.rmdir(temp_dir)
    except Exception as e:
        print(f"Error cleaning up temporary files: {e}")

def pdf_to_images(pdf_path, output_dir):
    """Convert PDF to images"""
    try:
        # Convert PDF to images
        images = convert_from_path(pdf_path)
        
        # Save each page as an image
        image_paths = []
        for i, image in enumerate(images):
            image_path = os.path.join(output_dir, f'page_{i + 1}.png')
            image.save(image_path, 'PNG')
            image_paths.append(image_path)
        
        return image_paths
    except Exception as e:
        raise ConversionError(f"Error converting PDF to images: {e}")

def images_to_pdf(image_paths, output_path):
    """Convert images to PDF"""
    try:
        # Convert images to PDF
        with open(output_path, "wb") as f:
            f.write(img2pdf.convert([Image.open(img_path).filename for img_path in image_paths]))
        return output_path
    except Exception as e:
        raise ConversionError(f"Error converting images to PDF: {e}")

def process_conversion(file_path, conversion_type):
    """Process file conversion based on type"""
    temp_dir = create_temp_directory()
    try:
        if conversion_type == 'pdf_to_img':
            # Convert PDF to images
            output_paths = pdf_to_images(file_path, temp_dir)
            # Create zip file of images
            zip_path = os.path.join(temp_dir, 'converted_images.zip')
            create_zip(output_paths, zip_path)
            return zip_path
        else:
            # Convert image to PDF
            output_path = os.path.join(temp_dir, 'converted.pdf')
            return images_to_pdf([file_path], output_path)
    except Exception as e:
        cleanup_temp_files(temp_dir)
        raise ConversionError(str(e))

def create_zip(file_paths, output_path):
    """Create a zip file from multiple files"""
    import zipfile
    try:
        with zipfile.ZipFile(output_path, 'w') as zipf:
            for file_path in file_paths:
                zipf.write(file_path, os.path.basename(file_path))
        return output_path
    except Exception as e:
        raise ConversionError(f"Error creating zip file: {e}")

def get_file_info(file_path):
    """Get file information"""
    try:
        return {
            'size': os.path.getsize(file_path),
            'created': datetime.fromtimestamp(os.path.getctime(file_path)),
            'modified': datetime.fromtimestamp(os.path.getmtime(file_path))
        }
    except Exception as e:
        raise ConversionError(f"Error getting file info: {e}")

def validate_file(file_path, conversion_type):
    """Validate file before conversion"""
    try:
        # Check file size
        file_size = os.path.getsize(file_path)
        max_size = 16 * 1024 * 1024  # 16MB
        if file_size > max_size:
            raise ConversionError("File size exceeds maximum limit (16MB)")

        # Check file type
        if conversion_type == 'pdf_to_img':
            if not file_path.lower().endswith('.pdf'):
                raise ConversionError("Invalid file type. Expected PDF file")
        else:
            valid_extensions = ['.jpg', '.jpeg', '.png']
            if not any(file_path.lower().endswith(ext) for ext in valid_extensions):
                raise ConversionError("Invalid file type. Expected JPG or PNG file")

        return True
    except ConversionError:
        raise
    except Exception as e:
        raise ConversionError(f"Error validating file: {e}")
