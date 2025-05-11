import json
import os
import base64
import uuid
import boto3
import fitz  # PyMuPDF
from PIL import Image
import io

s3_client = boto3.client('s3')
INPUT_BUCKET = os.environ['INPUT_BUCKET']
OUTPUT_BUCKET = os.environ['OUTPUT_BUCKET']

def lambda_handler(event, context):
    try:
        # Get file content from API Gateway
        if 'body' not in event:
            return response(400, {'message': 'No file content found'})
            
        # Check if the body is base64 encoded
        is_base64 = event.get('isBase64Encoded', False)
        body = event['body']
        
        if is_base64:
            body = base64.b64decode(body)
            
        # Get file information from headers
        headers = event.get('headers', {})
        content_type = headers.get('Content-Type', '')
        
        # Get source and target formats from query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        source_format = query_params.get('sourceFormat', '').lower()
        target_format = query_params.get('targetFormat', '').lower()
        
        # Validate formats
        supported_conversions = {
            'pdf-png': convert_pdf_to_png,
            'png-jpeg': convert_png_to_jpeg,
            'jpeg-png': convert_jpeg_to_png,
            'pdf-jpeg': convert_pdf_to_jpeg
        }
        
        conversion_key = f"{source_format}-{target_format}"
        if conversion_key not in supported_conversions:
            return response(400, {
                'message': f'Unsupported conversion: {source_format} to {target_format}',
                'supported_conversions': list(supported_conversions.keys())
            })
        
        # Generate unique filenames
        input_filename = f"{uuid.uuid4()}.{source_format}"
        output_filename = f"{uuid.uuid4()}.{target_format}"
        
        # Save input file to S3
        s3_client.put_object(
            Bucket=INPUT_BUCKET,
            Key=input_filename,
            Body=body
        )
        
        # Process the file based on conversion type
        conversion_function = supported_conversions[conversion_key]
        output_file_url = conversion_function(input_filename, output_filename)
        
        return response(200, {
            'message': 'File converted successfully',
            'output_url': output_file_url
        })
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return response(500, {'message': f'Conversion error: {str(e)}'})

def convert_pdf_to_png(input_filename, output_filename):
    # Download PDF from S3
    temp_input_path = f"/tmp/{input_filename}"
    s3_client.download_file(INPUT_BUCKET, input_filename, temp_input_path)
    
    # Convert PDF to PNG using PyMuPDF
    doc = fitz.open(temp_input_path)
    
    # For simplicity, convert only the first page
    page = doc.load_page(0)
    pix = page.get_pixmap()
    
    # Save PNG to memory
    png_data = pix.tobytes("png")
    
    # Upload PNG to S3
    s3_client.put_object(
        Bucket=OUTPUT_BUCKET,
        Key=output_filename,
        Body=png_data,
        ContentType='image/png'
    )
    
    # Clean up
    doc.close()
    os.remove(temp_input_path)
    
    # Generate presigned URL for the output file
    url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': OUTPUT_BUCKET, 'Key': output_filename},
        ExpiresIn=3600  # URL expires in 1 hour
    )
    
    return url

def convert_png_to_jpeg(input_filename, output_filename):
    # Download PNG from S3
    temp_input_path = f"/tmp/{input_filename}"
    s3_client.download_file(INPUT_BUCKET, input_filename, temp_input_path)
    
    # Convert PNG to JPEG using Pillow
    with Image.open(temp_input_path) as img:
        # Convert to RGB if necessary (for PNG with transparency)
        if img.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])  # 3 is the alpha channel
            img = background
        
        # Save as JPEG to memory
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=90)
        jpeg_data = buffer.getvalue()
    
    # Upload JPEG to S3
    s3_client.put_object(
        Bucket=OUTPUT_BUCKET,
        Key=output_filename,
        Body=jpeg_data,
        ContentType='image/jpeg'
    )
    
    # Clean up
    os.remove(temp_input_path)
    
    # Generate presigned URL for the output file
    url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': OUTPUT_BUCKET, 'Key': output_filename},
        ExpiresIn=3600  # URL expires in 1 hour
    )
    
    return url

def convert_jpeg_to_png(input_filename, output_filename):
    # Download JPEG from S3
    temp_input_path = f"/tmp/{input_filename}"
    s3_client.download_file(INPUT_BUCKET, input_filename, temp_input_path)
    
    # Convert JPEG to PNG using Pillow
    with Image.open(temp_input_path) as img:
        # Save as PNG to memory
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        png_data = buffer.getvalue()
    
    # Upload PNG to S3
    s3_client.put_object(
        Bucket=OUTPUT_BUCKET,
        Key=output_filename,
        Body=png_data,
        ContentType='image/png'
    )
    
    # Clean up
    os.remove(temp_input_path)
    
    # Generate presigned URL for the output file
    url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': OUTPUT_BUCKET, 'Key': output_filename},
        ExpiresIn=3600  # URL expires in 1 hour
    )
    
    return url

def convert_pdf_to_jpeg(input_filename, output_filename):
    # Download PDF from S3
    temp_input_path = f"/tmp/{input_filename}"
    s3_client.download_file(INPUT_BUCKET, input_filename, temp_input_path)
    
    # Convert PDF to PNG using PyMuPDF
    doc = fitz.open(temp_input_path)
    
    # For simplicity, convert only the first page
    page = doc.load_page(0)
    pix = page.get_pixmap()
    
    # Convert pixmap to PIL Image
    img_data = pix.tobytes("png")
    img = Image.open(io.BytesIO(img_data))
    
    # Convert to RGB if necessary
    if img.mode in ('RGBA', 'LA'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])  # 3 is the alpha channel
        img = background
    
    # Save as JPEG to memory
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=90)
    jpeg_data = buffer.getvalue()
    
    # Upload JPEG to S3
    s3_client.put_object(
        Bucket=OUTPUT_BUCKET,
        Key=output_filename,
        Body=jpeg_data,
        ContentType='image/jpeg'
    )
    
    # Clean up
    doc.close()
    os.remove(temp_input_path)
    
    # Generate presigned URL for the output file
    url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': OUTPUT_BUCKET, 'Key': output_filename},
        ExpiresIn=3600  # URL expires in 1 hour
    )
    
    return url

def response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
        },
        'body': json.dumps(body)
    }