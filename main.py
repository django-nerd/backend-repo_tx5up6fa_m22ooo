import os
from typing import List, Optional, Any, Dict
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime

# Database helpers
from database import db, create_document, get_documents
from schemas import Property, Inquiry

try:
    from bson import ObjectId
except Exception:
    ObjectId = None  # type: ignore

app = FastAPI(title="Real Estate Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Utilities
class PropertyOut(Property):
    id: str = Field(..., description="Document id")


def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return {}
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    # Convert datetime to isoformat for JSON
    for k, v in list(doc.items()):
        if isinstance(v, datetime):
            doc[k] = v.isoformat()
    return doc


@app.get("/")
def read_root():
    return {"message": "Real Estate API is running"}


@app.get("/api/hello")
def hello():
    return {"message": "Welcome to your real estate backend!"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = getattr(db, "name", None) or "Unknown"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# -------------------- Properties --------------------
@app.get("/api/properties", response_model=List[PropertyOut])
def list_properties(
    city: Optional[str] = None,
    property_type: Optional[str] = Query(None, description="House, Apartment, Condo, etc."),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    bedrooms: Optional[int] = Query(None, ge=0),
    bathrooms: Optional[float] = Query(None, ge=0),
    q: Optional[str] = Query(None, description="Free text search in title/description/city"),
    featured: Optional[bool] = None,
):
    try:
        filters: Dict[str, Any] = {}
        if city:
            filters["city"] = {"$regex": city, "$options": "i"}
        if property_type:
            filters["property_type"] = {"$regex": f"^{property_type}$", "$options": "i"}
        if featured is not None:
            filters["featured"] = featured
        price_cond: Dict[str, Any] = {}
        if min_price is not None:
            price_cond["$gte"] = min_price
        if max_price is not None:
            price_cond["$lte"] = max_price
        if price_cond:
            filters["price"] = price_cond
        if bedrooms is not None:
            filters["bedrooms"] = {"$gte": bedrooms}
        if bathrooms is not None:
            filters["bathrooms"] = {"$gte": bathrooms}
        if q:
            filters["$or"] = [
                {"title": {"$regex": q, "$options": "i"}},
                {"description": {"$regex": q, "$options": "i"}},
                {"city": {"$regex": q, "$options": "i"}},
                {"state": {"$regex": q, "$options": "i"}},
            ]

        docs = get_documents("property", filters)
        return [PropertyOut(**serialize_doc(d)) for d in docs]
    except Exception:
        # If DB not available, return empty list rather than erroring out
        return []


@app.get("/api/properties/featured", response_model=List[PropertyOut])
def featured_properties():
    try:
        docs = get_documents("property", {"featured": True})
        return [PropertyOut(**serialize_doc(d)) for d in docs]
    except Exception:
        return []


@app.get("/api/properties/{property_id}", response_model=PropertyOut)
def get_property(property_id: str):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    try:
        oid = ObjectId(property_id) if ObjectId else property_id
        doc = db["property"].find_one({"_id": oid})
        if not doc:
            raise HTTPException(status_code=404, detail="Property not found")
        return PropertyOut(**serialize_doc(doc))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid id: {str(e)}")


class SeedResult(BaseModel):
    inserted: int


@app.post("/api/setup/seed", response_model=SeedResult)
def seed_properties():
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    # Only seed if empty
    existing = db["property"].count_documents({})
    if existing > 0:
        return SeedResult(inserted=0)

    sample_data = [
        {
            "title": "Modern Family House",
            "description": "Spacious 4-bedroom home with open floor plan and large backyard.",
            "price": 549000,
            "address": "123 Maple Street",
            "city": "Springfield",
            "state": "IL",
            "zip_code": "62704",
            "bedrooms": 4,
            "bathrooms": 2.5,
            "area_sqft": 2400,
            "property_type": "House",
            "images": [
                "https://images.unsplash.com/photo-1572120360610-d971b9d7767c",
                "https://images.unsplash.com/photo-1560518883-ce09059eeffa"
            ],
            "amenities": ["Garage", "Garden", "Central Air"],
            "featured": True,
            "status": "For Sale",
            "listed_at": datetime.utcnow(),
        },
        {
            "title": "Downtown City Apartment",
            "description": "Stylish 2-bed apartment close to shops, cafes, and public transit.",
            "price": 329000,
            "address": "456 Oak Avenue, Apt 12B",
            "city": "Metro City",
            "state": "NY",
            "zip_code": "10001",
            "bedrooms": 2,
            "bathrooms": 1.0,
            "area_sqft": 900,
            "property_type": "Apartment",
            "images": [
                "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85",
                "https://images.unsplash.com/photo-1501183638710-841dd1904471"
            ],
            "amenities": ["Elevator", "Doorman", "Gym"],
            "featured": True,
            "status": "For Sale",
            "listed_at": datetime.utcnow(),
        },
        {
            "title": "Cozy Suburban Condo",
            "description": "Bright 1-bedroom condo with balcony and community pool.",
            "price": 189000,
            "address": "789 Pine Lane, Unit 305",
            "city": "Lakeside",
            "state": "CA",
            "zip_code": "92040",
            "bedrooms": 1,
            "bathrooms": 1.0,
            "area_sqft": 650,
            "property_type": "Condo",
            "images": [
                "https://images.unsplash.com/photo-1493809842364-78817add7ffb",
                "https://images.unsplash.com/photo-1512917774080-9991f1c4c750"
            ],
            "amenities": ["Pool", "Clubhouse"],
            "featured": False,
            "status": "For Sale",
            "listed_at": datetime.utcnow(),
        },
    ]

    inserted = 0
    for item in sample_data:
        try:
            create_document("property", item)
            inserted += 1
        except Exception:
            pass
    return SeedResult(inserted=inserted)


# -------------------- Inquiries --------------------
class InquiryResult(BaseModel):
    success: bool


@app.post("/api/inquiries", response_model=InquiryResult)
def create_inquiry(inquiry: Inquiry):
    try:
        create_document("inquiry", inquiry)
        return InquiryResult(success=True)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Could not save inquiry: {str(e)}")


# Optional: expose schemas for tooling/inspection
@app.get("/schema")
def get_schema():
    return {
        "collections": [
            {
                "name": "property",
                "schema": Property.model_json_schema(),
            },
            {
                "name": "inquiry",
                "schema": Inquiry.model_json_schema(),
            },
        ]
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
