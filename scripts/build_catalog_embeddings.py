#!/usr/bin/env python3
"""
Build CLIP Embeddings for Catalog Matching

Reads a CSV catalog file and builds CLIP image embeddings for visual matching.
The generated embeddings can be used by the ImageSearchService for CLIP-based matching.
"""

import argparse
import csv
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from tqdm import tqdm


def build_embeddings(
    catalog_csv: str,
    output_path: str,
    model_name: str = "openai/clip-vit-base-patch32",
    batch_size: int = 32
):
    """
    Build CLIP embeddings from catalog CSV.
    
    Args:
        catalog_csv: Path to catalog CSV with columns: sku, image_path, name
        output_path: Path to save embeddings (.npz file)
        model_name: CLIP model to use
        batch_size: Batch size for processing images
    """
    try:
        from transformers import CLIPProcessor, CLIPModel
        import torch
    except ImportError:
        print("✗ Error: transformers and torch are required")
        print("  Install with: pip install transformers torch")
        sys.exit(1)
    
    print(f"Loading CLIP model: {model_name}")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    
    model = CLIPModel.from_pretrained(model_name).to(device)
    processor = CLIPProcessor.from_pretrained(model_name)
    
    print(f"Reading catalog from: {catalog_csv}")
    items = []
    with open(catalog_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        required_cols = {'sku', 'name', 'image_path'}
        
        # Check if required columns exist
        if not required_cols.issubset(reader.fieldnames):
            print(f"✗ Error: CSV must have columns: {', '.join(required_cols)}")
            print(f"  Found columns: {', '.join(reader.fieldnames)}")
            sys.exit(1)
        
        for row in reader:
            items.append({
                'sku': row['sku'],
                'name': row['name'],
                'image_path': row['image_path']
            })
    
    print(f"Found {len(items)} items in catalog")
    
    if len(items) == 0:
        print("✗ Error: No items found in catalog")
        sys.exit(1)
    
    # Compute embeddings in batches
    embeddings = []
    skus = []
    names = []
    failed_count = 0
    
    for i in tqdm(range(0, len(items), batch_size), desc="Processing batches"):
        batch_items = items[i:i + batch_size]
        batch_images = []
        batch_skus = []
        batch_names = []
        
        # Load images for this batch
        for item in batch_items:
            try:
                image_path = item['image_path']
                if not os.path.exists(image_path):
                    print(f"⚠ Image not found: {image_path}")
                    failed_count += 1
                    continue
                    
                image = Image.open(image_path).convert("RGB")
                batch_images.append(image)
                batch_skus.append(item['sku'])
                batch_names.append(item['name'])
            except Exception as e:
                print(f"⚠ Failed to load {item['image_path']}: {e}")
                failed_count += 1
                continue
        
        if not batch_images:
            continue
        
        # Process batch
        try:
            inputs = processor(images=batch_images, return_tensors="pt", padding=True).to(device)
            
            with torch.no_grad():
                image_features = model.get_image_features(**inputs)
                # Normalize for cosine similarity
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            
            embeddings.extend(image_features.cpu().numpy())
            skus.extend(batch_skus)
            names.extend(batch_names)
        except Exception as e:
            print(f"⚠ Failed to process batch: {e}")
            failed_count += len(batch_images)
    
    if len(embeddings) == 0:
        print("✗ Error: No embeddings were generated")
        sys.exit(1)
    
    print(f"\nSuccessfully processed {len(embeddings)} items")
    if failed_count > 0:
        print(f"⚠ Failed to process {failed_count} items")
    
    # Save embeddings
    embeddings = np.array(embeddings)
    skus = np.array(skus)
    names = np.array(names)
    
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    np.savez(
        output_path,
        embeddings=embeddings,
        skus=skus,
        names=names
    )
    
    print(f"\n✓ Saved embeddings to: {output_path}")
    print(f"  Embeddings shape: {embeddings.shape}")
    print(f"  SKUs: {len(skus)}")
    print(f"  Names: {len(names)}")
    print(f"\nTo use these embeddings, ensure ImageSearchService is configured with:")
    print(f"  catalog_embeddings_path='{output_path}'")


def main():
    parser = argparse.ArgumentParser(
        description="Build CLIP embeddings from catalog CSV for visual matching",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build embeddings from catalog
  python scripts/build_catalog_embeddings.py

  # Custom paths
  python scripts/build_catalog_embeddings.py \\
    --catalog my_catalog.csv \\
    --output embeddings/catalog.npz

  # Use different CLIP model
  python scripts/build_catalog_embeddings.py \\
    --model openai/clip-vit-large-patch14

CSV Format:
  The catalog CSV must have columns: sku, image_path, name
  
  Example:
    sku,image_path,name
    56789,images/56789.jpg,Victorian House with Lights
    56790,images/56790.jpg,Christmas Church
        """
    )
    parser.add_argument(
        "--catalog",
        default="data/catalog.csv",
        help="Path to catalog CSV (columns: sku, image_path, name)"
    )
    parser.add_argument(
        "--output",
        default="data/catalog_embeddings.npz",
        help="Path to save embeddings (.npz file)"
    )
    parser.add_argument(
        "--model",
        default="openai/clip-vit-base-patch32",
        help="CLIP model to use (default: openai/clip-vit-base-patch32)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for processing (default: 32)"
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.catalog):
        print(f"✗ Catalog file not found: {args.catalog}")
        print(f"\nPlease create a CSV file with columns: sku, image_path, name")
        print(f"\nExample:")
        print(f"  sku,image_path,name")
        print(f'  "56789","images/56789.jpg","Victorian House with Lights"')
        print(f'  "56790","images/56790.jpg","Christmas Church"')
        return 1
    
    try:
        build_embeddings(
            catalog_csv=args.catalog,
            output_path=args.output,
            model_name=args.model,
            batch_size=args.batch_size
        )
        return 0
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
