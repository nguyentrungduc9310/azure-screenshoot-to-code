"""
Storage Manager for handling image storage
Supports local storage, Azure Blob Storage, and AWS S3
"""
import asyncio
import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import base64
import httpx

from app.core.config import Settings
from shared.monitoring.structured_logger import StructuredLogger

class StorageBackend(str, Enum):
    LOCAL = "local"
    AZURE_BLOB = "azure_blob"
    AWS_S3 = "s3"

@dataclass
class StoredImage:
    """Stored image information"""
    storage_id: str
    original_filename: str
    storage_path: str
    storage_url: Optional[str] = None
    content_type: str = "image/png"
    size_bytes: int = 0
    created_at: datetime = None
    metadata: Dict[str, Any] = None

class StorageManager:
    """Manages image storage across different backends"""
    
    def __init__(self, settings: Settings, logger: StructuredLogger):
        self.settings = settings
        self.logger = logger
        self.backend = StorageBackend(settings.storage_backend)
        
        # Initialize storage clients
        self.azure_client = None
        self.s3_client = None
        
        # Setup local storage path
        if self.backend == StorageBackend.LOCAL:
            self.local_path = Path(settings.local_storage_path)
            self.local_path.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self):
        """Initialize storage backend"""
        self.logger.info("Initializing storage backend", backend=self.backend.value)
        
        if self.backend == StorageBackend.AZURE_BLOB:
            await self._initialize_azure_blob()
        elif self.backend == StorageBackend.AWS_S3:
            await self._initialize_aws_s3()
        elif self.backend == StorageBackend.LOCAL:
            self._initialize_local_storage()
        
        self.logger.info("Storage backend initialized successfully", backend=self.backend.value)
    
    async def _initialize_azure_blob(self):
        """Initialize Azure Blob Storage"""
        try:
            from azure.storage.blob.aio import BlobServiceClient
            
            if not self.settings.has_azure_storage_config:
                raise ValueError("Azure Blob Storage configuration is incomplete")
            
            self.azure_client = BlobServiceClient.from_connection_string(
                self.settings.azure_storage_connection_string
            )
            
            # Ensure container exists
            container_client = self.azure_client.get_container_client(
                self.settings.azure_storage_container
            )
            
            try:
                await container_client.create_container()
                self.logger.info("Created Azure Blob container", 
                               container=self.settings.azure_storage_container)
            except Exception:
                # Container likely already exists
                pass
                
        except ImportError:
            raise ValueError("Azure Blob Storage dependencies not installed. Run: pip install azure-storage-blob")
        except Exception as e:
            raise ValueError(f"Failed to initialize Azure Blob Storage: {str(e)}")
    
    async def _initialize_aws_s3(self):
        """Initialize AWS S3"""
        try:
            import aioboto3
            
            if not self.settings.has_s3_config:
                raise ValueError("AWS S3 configuration is incomplete")
            
            session = aioboto3.Session()
            self.s3_client = session.client(
                's3',
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
                region_name=self.settings.aws_region
            )
            
            # Check if bucket exists (this will raise an exception if it doesn't)
            async with self.s3_client as s3:
                await s3.head_bucket(Bucket=self.settings.aws_s3_bucket)
                
        except ImportError:
            raise ValueError("AWS S3 dependencies not installed. Run: pip install aioboto3")
        except Exception as e:
            raise ValueError(f"Failed to initialize AWS S3: {str(e)}")
    
    def _initialize_local_storage(self):
        """Initialize local storage"""
        try:
            # Create directory structure
            self.local_path.mkdir(parents=True, exist_ok=True)
            
            # Create subdirectories by date
            today = datetime.now().strftime("%Y/%m/%d")
            (self.local_path / today).mkdir(parents=True, exist_ok=True)
            
        except Exception as e:
            raise ValueError(f"Failed to initialize local storage: {str(e)}")
    
    async def store_image(
        self, 
        image_data: bytes, 
        filename: str, 
        content_type: str = "image/png",
        metadata: Optional[Dict[str, Any]] = None
    ) -> StoredImage:
        """Store image data and return storage information"""
        
        # Generate unique storage ID
        storage_id = self._generate_storage_id(image_data, filename)
        
        # Add timestamp to metadata
        if metadata is None:
            metadata = {}
        metadata.update({
            "created_at": datetime.now().isoformat(),
            "original_filename": filename,
            "content_type": content_type
        })
        
        self.logger.info("Storing image", 
                        storage_id=storage_id,
                        filename=filename,
                        size_bytes=len(image_data),
                        backend=self.backend.value)
        
        try:
            if self.backend == StorageBackend.LOCAL:
                stored_image = await self._store_local(storage_id, image_data, filename, content_type, metadata)
            elif self.backend == StorageBackend.AZURE_BLOB:
                stored_image = await self._store_azure_blob(storage_id, image_data, filename, content_type, metadata)
            elif self.backend == StorageBackend.AWS_S3:
                stored_image = await self._store_aws_s3(storage_id, image_data, filename, content_type, metadata)
            else:
                raise ValueError(f"Unsupported storage backend: {self.backend}")
            
            self.logger.info("Image stored successfully",
                           storage_id=storage_id,
                           storage_path=stored_image.storage_path,
                           backend=self.backend.value)
            
            return stored_image
            
        except Exception as e:
            self.logger.error("Failed to store image",
                            storage_id=storage_id,
                            error=str(e),
                            backend=self.backend.value)
            raise
    
    async def _store_local(
        self, 
        storage_id: str, 
        image_data: bytes, 
        filename: str, 
        content_type: str,
        metadata: Dict[str, Any]
    ) -> StoredImage:
        """Store image in local filesystem"""
        
        # Create date-based directory structure
        today = datetime.now().strftime("%Y/%m/%d")
        storage_dir = self.local_path / today
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine file extension
        ext = Path(filename).suffix or '.png'
        storage_filename = f"{storage_id}{ext}"
        storage_path = storage_dir / storage_filename
        
        # Write image data
        with open(storage_path, 'wb') as f:
            f.write(image_data)
        
        # Write metadata
        import json
        metadata_path = storage_dir / f"{storage_id}.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return StoredImage(
            storage_id=storage_id,
            original_filename=filename,
            storage_path=str(storage_path),
            storage_url=f"file://{storage_path.absolute()}",
            content_type=content_type,
            size_bytes=len(image_data),
            created_at=datetime.now(),
            metadata=metadata
        )
    
    async def _store_azure_blob(
        self, 
        storage_id: str, 
        image_data: bytes, 
        filename: str, 
        content_type: str,
        metadata: Dict[str, Any]
    ) -> StoredImage:
        """Store image in Azure Blob Storage"""
        
        # Create blob name with date structure
        today = datetime.now().strftime("%Y/%m/%d")
        ext = Path(filename).suffix or '.png'
        blob_name = f"{today}/{storage_id}{ext}"
        
        # Get blob client
        blob_client = self.azure_client.get_blob_client(
            container=self.settings.azure_storage_container,
            blob=blob_name
        )
        
        # Upload blob
        await blob_client.upload_blob(
            image_data,
            content_type=content_type,
            metadata=metadata,
            overwrite=True
        )
        
        # Generate public URL
        storage_url = f"https://{blob_client.account_name}.blob.core.windows.net/{self.settings.azure_storage_container}/{blob_name}"
        
        return StoredImage(
            storage_id=storage_id,
            original_filename=filename,
            storage_path=blob_name,
            storage_url=storage_url,
            content_type=content_type,
            size_bytes=len(image_data),
            created_at=datetime.now(),
            metadata=metadata
        )
    
    async def _store_aws_s3(
        self, 
        storage_id: str, 
        image_data: bytes, 
        filename: str, 
        content_type: str,
        metadata: Dict[str, Any]
    ) -> StoredImage:
        """Store image in AWS S3"""
        
        # Create S3 key with date structure
        today = datetime.now().strftime("%Y/%m/%d")
        ext = Path(filename).suffix or '.png'
        s3_key = f"{today}/{storage_id}{ext}"
        
        # Prepare S3 metadata (must be strings)
        s3_metadata = {k: str(v) for k, v in metadata.items()}
        
        # Upload to S3
        async with self.s3_client as s3:
            await s3.put_object(
                Bucket=self.settings.aws_s3_bucket,
                Key=s3_key,
                Body=image_data,
                ContentType=content_type,
                Metadata=s3_metadata
            )
        
        # Generate public URL
        storage_url = f"https://{self.settings.aws_s3_bucket}.s3.{self.settings.aws_region}.amazonaws.com/{s3_key}"
        
        return StoredImage(
            storage_id=storage_id,
            original_filename=filename,
            storage_path=s3_key,
            storage_url=storage_url,
            content_type=content_type,
            size_bytes=len(image_data),
            created_at=datetime.now(),
            metadata=metadata
        )
    
    async def retrieve_image(self, storage_id: str) -> Optional[bytes]:
        """Retrieve image data by storage ID"""
        self.logger.info("Retrieving image", storage_id=storage_id, backend=self.backend.value)
        
        try:
            if self.backend == StorageBackend.LOCAL:
                return await self._retrieve_local(storage_id)
            elif self.backend == StorageBackend.AZURE_BLOB:
                return await self._retrieve_azure_blob(storage_id)
            elif self.backend == StorageBackend.AWS_S3:
                return await self._retrieve_aws_s3(storage_id)
            else:
                raise ValueError(f"Unsupported storage backend: {self.backend}")
                
        except Exception as e:
            self.logger.error("Failed to retrieve image",
                            storage_id=storage_id,
                            error=str(e),
                            backend=self.backend.value)
            return None
    
    async def _retrieve_local(self, storage_id: str) -> Optional[bytes]:
        """Retrieve image from local storage"""
        # Search for the image file (we need to find it by storage_id)
        for root, dirs, files in os.walk(self.local_path):
            for file in files:
                if file.startswith(storage_id) and not file.endswith('.json'):
                    file_path = Path(root) / file
                    with open(file_path, 'rb') as f:
                        return f.read()
        return None
    
    async def _retrieve_azure_blob(self, storage_id: str) -> Optional[bytes]:
        """Retrieve image from Azure Blob Storage"""
        # List blobs to find the one with matching storage_id
        container_client = self.azure_client.get_container_client(
            self.settings.azure_storage_container
        )
        
        async for blob in container_client.list_blobs():
            if storage_id in blob.name:
                blob_client = self.azure_client.get_blob_client(
                    container=self.settings.azure_storage_container,
                    blob=blob.name
                )
                download_stream = await blob_client.download_blob()
                return await download_stream.readall()
        return None
    
    async def _retrieve_aws_s3(self, storage_id: str) -> Optional[bytes]:
        """Retrieve image from AWS S3"""
        async with self.s3_client as s3:
            # List objects to find the one with matching storage_id
            response = await s3.list_objects_v2(Bucket=self.settings.aws_s3_bucket)
            
            for obj in response.get('Contents', []):
                if storage_id in obj['Key']:
                    obj_response = await s3.get_object(
                        Bucket=self.settings.aws_s3_bucket,
                        Key=obj['Key']
                    )
                    return await obj_response['Body'].read()
        return None
    
    async def delete_image(self, storage_id: str) -> bool:
        """Delete image by storage ID"""
        self.logger.info("Deleting image", storage_id=storage_id, backend=self.backend.value)
        
        try:
            if self.backend == StorageBackend.LOCAL:
                return await self._delete_local(storage_id)
            elif self.backend == StorageBackend.AZURE_BLOB:
                return await self._delete_azure_blob(storage_id)
            elif self.backend == StorageBackend.AWS_S3:
                return await self._delete_aws_s3(storage_id)
            else:
                raise ValueError(f"Unsupported storage backend: {self.backend}")
                
        except Exception as e:
            self.logger.error("Failed to delete image",
                            storage_id=storage_id,
                            error=str(e),
                            backend=self.backend.value)
            return False
    
    async def _delete_local(self, storage_id: str) -> bool:
        """Delete image from local storage"""
        deleted = False
        for root, dirs, files in os.walk(self.local_path):
            for file in files:
                if file.startswith(storage_id):
                    file_path = Path(root) / file
                    file_path.unlink()
                    deleted = True
        return deleted
    
    async def _delete_azure_blob(self, storage_id: str) -> bool:
        """Delete image from Azure Blob Storage"""
        container_client = self.azure_client.get_container_client(
            self.settings.azure_storage_container
        )
        
        deleted = False
        async for blob in container_client.list_blobs():
            if storage_id in blob.name:
                blob_client = self.azure_client.get_blob_client(
                    container=self.settings.azure_storage_container,
                    blob=blob.name
                )
                await blob_client.delete_blob()
                deleted = True
        return deleted
    
    async def _delete_aws_s3(self, storage_id: str) -> bool:
        """Delete image from AWS S3"""
        async with self.s3_client as s3:
            response = await s3.list_objects_v2(Bucket=self.settings.aws_s3_bucket)
            
            deleted = False
            for obj in response.get('Contents', []):
                if storage_id in obj['Key']:
                    await s3.delete_object(
                        Bucket=self.settings.aws_s3_bucket,
                        Key=obj['Key']
                    )
                    deleted = True
            return deleted
    
    def _generate_storage_id(self, image_data: bytes, filename: str) -> str:
        """Generate unique storage ID based on image data and filename"""
        # Create hash from image data and filename
        hasher = hashlib.sha256()
        hasher.update(image_data)
        hasher.update(filename.encode('utf-8'))
        hasher.update(datetime.now().isoformat().encode('utf-8'))
        
        return hasher.hexdigest()[:16]  # Use first 16 characters
    
    async def store_image_from_url(self, image_url: str, filename: str) -> Optional[StoredImage]:
        """Download and store image from URL"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(image_url)
                response.raise_for_status()
                
                # Determine content type
                content_type = response.headers.get('content-type', 'image/png')
                
                # Store the image
                return await self.store_image(
                    image_data=response.content,
                    filename=filename,
                    content_type=content_type,
                    metadata={"source_url": image_url}
                )
                
        except Exception as e:
            self.logger.error("Failed to store image from URL",
                            url=image_url,
                            error=str(e))
            return None
    
    async def store_image_from_base64(self, base64_data: str, filename: str) -> Optional[StoredImage]:
        """Store image from base64 data"""
        try:
            # Decode base64 data
            image_data = base64.b64decode(base64_data)
            
            # Store the image
            return await self.store_image(
                image_data=image_data,
                filename=filename,
                content_type="image/png",
                metadata={"source": "base64"}
            )
            
        except Exception as e:
            self.logger.error("Failed to store image from base64",
                            error=str(e))
            return None
    
    async def cleanup(self):
        """Cleanup storage connections"""
        if self.azure_client:
            await self.azure_client.close()
        
        self.logger.info("Storage cleanup complete")