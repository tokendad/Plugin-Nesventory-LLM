# API Error Codes Reference

This document describes the error codes returned by the NesVentory LLM Plugin API and how to handle them.

## Error Response Structure

All API errors return a consistent JSON structure in the `detail` field:

```json
{
  "detail": {
    "error": "Error category",
    "message": "Human-readable description",
    "error_code": "MACHINE_READABLE_CODE",
    "details": {},  // Optional: Additional context
    "file_info": {},  // Optional: File-related errors
    "suggestions": []  // Optional: Resolution suggestions
  }
}
```

## Error Codes

### Service Availability Errors (5xx)

#### KB_NOT_INITIALIZED
**HTTP Status:** 503 Service Unavailable  
**Description:** The knowledge base has not been initialized  
**Resolution:** The service is starting up or encountered an initialization error. Wait a few moments and retry.

#### IMAGE_SEARCH_SERVICE_UNAVAILABLE
**HTTP Status:** 503 Service Unavailable  
**Description:** The image search service failed to initialize  
**Resolution:** 
- Check that `transformers` and `torch` packages are installed
- Review server logs for initialization errors
- Restart the service

### Client Errors (4xx)

#### INVALID_FILE_TYPE
**HTTP Status:** 400 Bad Request  
**Endpoints:** `/search/image`, `/nesventory/identify/image`  
**Description:** Uploaded file is not an image  
**Fields:**
- `file_info.content_type`: The actual content type received
- `file_info.filename`: Name of the uploaded file

**Resolution:**
- Upload a valid image file (JPEG, PNG, WebP, or BMP)
- Check that the file extension matches the actual format

#### EMPTY_FILE
**HTTP Status:** 400 Bad Request  
**Endpoints:** `/search/image`, `/nesventory/identify/image`  
**Description:** Uploaded file contains no data  
**Fields:**
- `file_info.filename`: Name of the uploaded file
- `file_info.size_bytes`: Always 0

**Resolution:**
- Verify the file contains valid data
- Try uploading a different file

#### INVALID_IMAGE_DATA
**HTTP Status:** 400 Bad Request  
**Endpoints:** `/search/image`, `/nesventory/identify/image`  
**Description:** File claims to be an image but cannot be parsed  
**Fields:**
- `file_info.filename`: Name of the uploaded file
- `file_info.content_type`: Declared content type
- `file_info.size_bytes`: File size in bytes

**Resolution:**
- Ensure the file is a valid, uncorrupted image
- Try converting the image to a standard format (PNG or JPEG)
- Use an image validation tool to check file integrity

#### ITEM_ALREADY_EXISTS
**HTTP Status:** 409 Conflict  
**Endpoints:** `/items/add`  
**Description:** Attempting to add an item with a duplicate ID  
**Fields:**
- `details.item_id`: The duplicate ID
- `details.existing_name`: Name of the existing item

**Resolution:**
- Use a different item ID
- Update the existing item instead
- Check if you're adding the correct item

### Database Errors (4xx)

#### Database Empty
**HTTP Status:** 404 Not Found  
**Endpoints:** `/query`, `/search`, `/build`, `/items/{id}`, `/nesventory/identify`  
**Description:** No items are loaded in the knowledge base  
**Fields:**
- `items_loaded`: Always 0

**Resolution:**
- Use the `/scrape` endpoint to fetch data first
- Check that data files exist in the data directory

#### Item Not Found
**HTTP Status:** 404 Not Found  
**Endpoints:** `/items/{id}`  
**Description:** Requested item ID does not exist  
**Fields:**
- `items_loaded`: Number of items currently loaded
- `item_id`: The ID that was not found

**Resolution:**
- Verify the item ID is correct
- Use `/items` to list available items
- Check if the item exists in the source data

### Processing Errors (5xx)

#### IMAGE_SEARCH_ERROR
**HTTP Status:** 500 Internal Server Error  
**Endpoints:** `/search/image`  
**Description:** Unexpected error during image search  
**Fields:**
- `details.error_type`: Python exception type
- `details.error_message`: Exception message

**Resolution:**
- Try with a different image
- Check server logs for details
- Contact support if persistent

#### IMAGE_IDENTIFICATION_ERROR
**HTTP Status:** 500 Internal Server Error  
**Endpoints:** `/nesventory/identify/image`  
**Description:** Unexpected error during image identification  
**Fields:**
- `details.error_type`: Python exception type
- `details.error_message`: Exception message

**Resolution:**
- Try with a different image
- Check server logs for details
- Contact support if persistent

#### SCRAPING_ERROR
**HTTP Status:** 500 Internal Server Error  
**Endpoints:** `/scrape`  
**Description:** Failed to scrape data from configured source  
**Fields:**
- `details.mode`: Scraping mode (local/remote/internet)
- `details.error_type`: Python exception type
- `details.error_message`: Exception message

**Resolution:**
- **LOCAL mode:** Verify data files exist
- **REMOTE/INTERNET mode:** Check network connectivity
- Review server logs for detailed error information

#### EMBEDDING_BUILD_ERROR
**HTTP Status:** 500 Internal Server Error  
**Endpoints:** `/build`  
**Description:** Failed to generate semantic search embeddings  
**Fields:**
- `details.items_count`: Number of items attempted
- `details.error_type`: Python exception type
- `details.error_message`: Exception message

**Resolution:**
- Ensure sufficient memory is available
- Verify the embedding model is installed
- Check that items have valid text content
- Review server logs

## Programmatic Error Handling

### Example: Python Client

```python
import requests

def upload_image(image_path):
    with open(image_path, 'rb') as f:
        response = requests.post(
            'http://localhost:8002/search/image',
            files={'file': f}
        )
    
    if response.status_code == 200:
        return response.json()
    
    # Handle errors
    error = response.json()['detail']
    
    if isinstance(error, dict):
        error_code = error.get('error_code')
        
        if error_code == 'INVALID_FILE_TYPE':
            print(f"Invalid file type: {error['file_info']['content_type']}")
            print("Suggestions:", error['suggestions'])
        elif error_code == 'IMAGE_SEARCH_SERVICE_UNAVAILABLE':
            print("Service unavailable, please try again later")
        else:
            print(f"Error: {error['message']}")
    else:
        # Legacy string error
        print(f"Error: {error}")
    
    return None
```

### Example: JavaScript Client

```javascript
async function uploadImage(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('http://localhost:8002/search/image', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            return await response.json();
        }
        
        const error = await response.json();
        const detail = error.detail;
        
        if (typeof detail === 'object') {
            switch (detail.error_code) {
                case 'INVALID_FILE_TYPE':
                    console.error('Invalid file:', detail.file_info.content_type);
                    console.log('Suggestions:', detail.suggestions);
                    break;
                case 'EMPTY_FILE':
                    console.error('File is empty');
                    break;
                case 'IMAGE_SEARCH_SERVICE_UNAVAILABLE':
                    console.error('Service temporarily unavailable');
                    break;
                default:
                    console.error(detail.message);
            }
        } else {
            console.error('Error:', detail);
        }
        
        return null;
    } catch (err) {
        console.error('Network error:', err);
        return null;
    }
}
```

## Best Practices

1. **Always check error_code first** - Use the machine-readable error code for logic, not string matching
2. **Display suggestions to users** - The suggestions array contains actionable steps
3. **Log detailed errors** - Include `details` and `file_info` fields in logs for debugging
4. **Implement retries** - For 503 errors, implement exponential backoff
5. **Validate client-side** - Check file types and sizes before uploading to reduce errors
6. **Monitor error rates** - Track error codes to identify common issues

## Migration from Simple Errors

Previous versions of the API returned simple string errors:

```json
{
  "detail": "Knowledge base not initialized"
}
```

New versions return structured errors:

```json
{
  "detail": {
    "error": "Service unavailable",
    "message": "Knowledge base not initialized",
    "error_code": "KB_NOT_INITIALIZED"
  }
}
```

**Backward Compatibility:** To handle both formats:

```python
error = response.json()['detail']

if isinstance(error, dict):
    # New structured format
    message = error['message']
    code = error.get('error_code')
else:
    # Legacy string format
    message = error
    code = None
```
