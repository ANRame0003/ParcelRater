"""
Parcel Rate Finder – FastAPI Backend
Supports: UPS, FedEx, DHL Express
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import asyncio
import base64
from typing import Optional, List

app = FastAPI(title="Parcel Rate Finder API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Models ───────────────────────────────────────────────────────────────────

class Credentials(BaseModel):
    ups_client_id: str = ""
    ups_client_secret: str = ""
    fedex_client_id: str = ""
    fedex_client_secret: str = ""
    dhl_api_key: str = ""

class RateRequest(BaseModel):
    origin_zip: str
    origin_country: str
    dest_zip: str
    dest_country: str
    weight: float
    weight_unit: str = "LBS"        # LBS or KGS
    length: float = 0
    width: float = 0
    height: float = 0
    dim_unit: str = "IN"            # IN or CM
    ship_date: str                  # YYYY-MM-DD
    signature_required: bool = False
    saturday_delivery: bool = False
    residential: bool = False
    credentials: Credentials

class RateResult(BaseModel):
    carrier: str
    service_name: str
    service_code: str
    total_charge: float
    freight_charge: float
    fuel_surcharge: float
    accessorial_charges: float
    currency: str
    estimated_delivery: Optional[str] = None
    transit_days: Optional[int] = None
    error: Optional[str] = None

# ─── Helpers ──────────────────────────────────────────────────────────────────

def to_lbs(weight: float, unit: str) -> float:
    return weight if unit == "LBS" else weight * 2.20462

def to_kg(weight: float, unit: str) -> float:
    return weight if unit == "KGS" else weight * 0.453592

def to_inches(val: float, unit: str) -> float:
    return val if unit == "IN" else val / 2.54

def to_cm(val: float, unit: str) -> float:
    return val if unit == "CM" else val * 2.54

# ─── UPS Service Codes ────────────────────────────────────────────────────────

UPS_SERVICES = {
    "01": "Next Day Air",
    "02": "2nd Day Air",
    "03": "Ground",
    "07": "Worldwide Express",
    "08": "Worldwide Expedited",
    "11": "Standard",
    "12": "3 Day Select",
    "13": "Next Day Air Saver",
    "14": "Next Day Air Early",
    "54": "Worldwide Express Plus",
    "59": "2nd Day Air AM",
    "65": "Worldwide Saver",
    "70": "Access Point Economy",
    "93": "Sure Post",
}

# ─── FedEx Service Types ──────────────────────────────────────────────────────

FEDEX_SERVICES = {
    "FEDEX_GROUND": "Ground",
    "FEDEX_HOME_DELIVERY": "Home Delivery",
    "FEDEX_2_DAY": "2Day",
    "FEDEX_2_DAY_AM": "2Day AM",
    "FEDEX_EXPRESS_SAVER": "Express Saver",
    "STANDARD_OVERNIGHT": "Standard Overnight",
    "PRIORITY_OVERNIGHT": "Priority Overnight",
    "FIRST_OVERNIGHT": "First Overnight",
    "INTERNATIONAL_ECONOMY": "International Economy",
    "INTERNATIONAL_PRIORITY": "International Priority",
    "FEDEX_INTERNATIONAL_PRIORITY_EXPRESS": "Intl Priority Express",
    "SMART_POST": "SmartPost",
    "GROUND_HOME_DELIVERY": "Ground Home Delivery",
}

FEDEX_TRANSIT_MAP = {
    "ONE_DAY": 1, "TWO_DAYS": 2, "THREE_DAYS": 3,
    "FOUR_DAYS": 4, "FIVE_DAYS": 5, "SIX_DAYS": 6,
    "SEVEN_DAYS": 7,
}

# ─── UPS ──────────────────────────────────────────────────────────────────────

async def get_ups_token(client_id: str, client_secret: str) -> str:
    creds_b64 = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://onlinetools.ups.com/security/v1/oauth/token",
            headers={
                "Authorization": f"Basic {creds_b64}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()["access_token"]


async def get_ups_rates(req: RateRequest) -> List[RateResult]:
    if not req.credentials.ups_client_id or not req.credentials.ups_client_secret:
        return [RateResult(
            carrier="UPS", service_name="—", service_code="",
            total_charge=0, freight_charge=0, fuel_surcharge=0,
            accessorial_charges=0, currency="USD",
            error="No UPS credentials provided",
        )]
    try:
        token = await get_ups_token(
            req.credentials.ups_client_id,
            req.credentials.ups_client_secret,
        )

        weight_lbs = round(to_lbs(req.weight, req.weight_unit), 1)
        length_in  = round(to_inches(req.length, req.dim_unit), 1)
        width_in   = round(to_inches(req.width,  req.dim_unit), 1)
        height_in  = round(to_inches(req.height, req.dim_unit), 1)
        has_dims   = length_in > 0 and width_in > 0 and height_in > 0

        pkg_options: dict = {}
        if req.signature_required:
            pkg_options["DeliveryConfirmation"] = {"DCISType": "2"}

        shipment_options: dict = {}
        if req.saturday_delivery:
            shipment_options["SaturdayDeliveryIndicator"] = ""

        payload = {
            "RateRequest": {
                "Request": {"RequestOption": "Shop"},
                "Shipment": {
                    "Shipper": {
                        "Address": {
                            "PostalCode": req.origin_zip,
                            "CountryCode": req.origin_country,
                        }
                    },
                    "ShipTo": {
                        "Address": {
                            "PostalCode": req.dest_zip,
                            "CountryCode": req.dest_country,
                            **({"ResidentialAddressIndicator": ""} if req.residential else {}),
                        }
                    },
                    "ShipFrom": {
                        "Address": {
                            "PostalCode": req.origin_zip,
                            "CountryCode": req.origin_country,
                        }
                    },
                    "Package": {
                        "PackagingType": {"Code": "02"},
                        **({"Dimensions": {
                            "UnitOfMeasurement": {"Code": "IN"},
                            "Length": str(length_in),
                            "Width":  str(width_in),
                            "Height": str(height_in),
                        }} if has_dims else {}),
                        "PackageWeight": {
                            "UnitOfMeasurement": {"Code": "LBS"},
                            "Weight": str(weight_lbs),
                        },
                        **({"PackageServiceOptions": pkg_options} if pkg_options else {}),
                    },
                    **({"ShipmentServiceOptions": shipment_options} if shipment_options else {}),
                    "DeliveryTimeInformation": {
                        "PackageBillType": "02",
                        "Pickup": {"Date": req.ship_date.replace("-", "")},
                    },
                },
            }
        }

        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://onlinetools.ups.com/api/rating/v2403/Shop",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "transId": "rate-finder",
                    "transactionSrc": "RateFinder",
                },
                json=payload,
                timeout=25,
            )
            r.raise_for_status()
            data = r.json()

        results = []
        shipments = data.get("RateResponse", {}).get("RatedShipment", [])
        if isinstance(shipments, dict):
            shipments = [shipments]

        for s in shipments:
            svc_code = s.get("Service", {}).get("Code", "")
            svc_name  = UPS_SERVICES.get(svc_code, f"UPS Service {svc_code}")
            total     = float(s.get("TotalCharges", {}).get("MonetaryValue", 0))
            freight   = float(s.get("TransportationCharges", {}).get("MonetaryValue", 0))
            svc_opts  = float(s.get("ServiceOptionsCharges", {}).get("MonetaryValue", 0))
            currency  = s.get("TotalCharges", {}).get("CurrencyCode", "USD")

            # Fuel surcharge from itemised package charges (code 375)
            fuel = 0.0
            pkgs = s.get("RatedPackage", [])
            if isinstance(pkgs, dict):
                pkgs = [pkgs]
            for pkg in pkgs:
                items = pkg.get("ItemizedCharges", [])
                if isinstance(items, dict):
                    items = [items]
                for charge in items:
                    if charge.get("Code") == "375":
                        fuel += float(charge.get("MonetaryValue", 0))

            # Accessorials = total - freight - fuel (or service options if positive)
            accessorials = max(total - freight - fuel, 0) if (total - freight - fuel) > 0.01 else svc_opts

            # Delivery date from time-in-transit
            delivery_date = None
            transit_days  = None
            tit = s.get("TimeInTransit", {})
            if tit:
                arrival = (
                    tit.get("ServiceSummary", {})
                       .get("EstimatedArrival", {})
                       .get("Arrival", {})
                       .get("Date", "")
                )
                if arrival and len(arrival) == 8:
                    delivery_date = f"{arrival[:4]}-{arrival[4:6]}-{arrival[6:]}"
                td = tit.get("ServiceSummary", {}).get("EstimatedArrival", {}).get("BusinessDaysInTransit")
                if td:
                    try:
                        transit_days = int(td)
                    except ValueError:
                        pass

            results.append(RateResult(
                carrier="UPS",
                service_name=f"UPS {svc_name}",
                service_code=svc_code,
                total_charge=round(total, 2),
                freight_charge=round(freight, 2),
                fuel_surcharge=round(fuel, 2),
                accessorial_charges=round(accessorials, 2),
                currency=currency,
                estimated_delivery=delivery_date,
                transit_days=transit_days,
            ))

        return results or [RateResult(
            carrier="UPS", service_name="No rates returned", service_code="",
            total_charge=0, freight_charge=0, fuel_surcharge=0,
            accessorial_charges=0, currency="USD",
            error="UPS returned no rates for this shipment",
        )]

    except httpx.HTTPStatusError as exc:
        return [RateResult(
            carrier="UPS", service_name="Error", service_code="",
            total_charge=0, freight_charge=0, fuel_surcharge=0,
            accessorial_charges=0, currency="USD",
            error=f"HTTP {exc.response.status_code}: {exc.response.text[:300]}",
        )]
    except Exception as exc:
        return [RateResult(
            carrier="UPS", service_name="Error", service_code="",
            total_charge=0, freight_charge=0, fuel_surcharge=0,
            accessorial_charges=0, currency="USD",
            error=str(exc),
        )]


# ─── FedEx ────────────────────────────────────────────────────────────────────

async def get_fedex_token(client_id: str, client_secret: str) -> str:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://apis.fedex.com/oauth/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=15,
        )
        r.raise_for_status()
        return r.json()["access_token"]


async def get_fedex_rates(req: RateRequest) -> List[RateResult]:
    if not req.credentials.fedex_client_id or not req.credentials.fedex_client_secret:
        return [RateResult(
            carrier="FedEx", service_name="—", service_code="",
            total_charge=0, freight_charge=0, fuel_surcharge=0,
            accessorial_charges=0, currency="USD",
            error="No FedEx credentials provided",
        )]
    try:
        token = await get_fedex_token(
            req.credentials.fedex_client_id,
            req.credentials.fedex_client_secret,
        )

        weight_kg = round(to_kg(req.weight, req.weight_unit), 3)
        length_cm = round(to_cm(req.length, req.dim_unit))
        width_cm  = round(to_cm(req.width,  req.dim_unit))
        height_cm = round(to_cm(req.height, req.dim_unit))
        has_dims  = length_cm > 0 and width_cm > 0 and height_cm > 0

        pkg_svc_types: list = []
        ship_svc_types: list = []
        pkg_svc_options: dict = {}

        if req.signature_required:
            pkg_svc_types.append("SIGNATURE_OPTION")
            pkg_svc_options["signatureOptionType"] = "INDIRECT"
        if req.saturday_delivery:
            ship_svc_types.append("SATURDAY_DELIVERY")

        package = {
            "weight": {"units": "KG", "value": weight_kg},
            **({"dimensions": {
                "length": length_cm,
                "width":  width_cm,
                "height": height_cm,
                "units": "CM",
            }} if has_dims else {}),
        }
        if pkg_svc_types:
            package["packageSpecialServices"] = {
                "specialServiceTypes": pkg_svc_types,
                **pkg_svc_options,
            }

        shipment: dict = {
            "shipper": {
                "address": {
                    "postalCode": req.origin_zip,
                    "countryCode": req.origin_country,
                    "residential": False,
                }
            },
            "recipient": {
                "address": {
                    "postalCode": req.dest_zip,
                    "countryCode": req.dest_country,
                    "residential": req.residential,
                }
            },
            "pickupType": "DROPOFF_AT_FEDEX_LOCATION",
            "rateRequestType": ["LIST"],
            "shipDateStamp": req.ship_date,
            "requestedPackageLineItems": [package],
        }
        if ship_svc_types:
            shipment["shipmentSpecialServices"] = {"specialServiceTypes": ship_svc_types}

        payload = {"requestedShipment": shipment}

        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://apis.fedex.com/rate/v1/rates/quotes",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "X-locale": "en_US",
                },
                json=payload,
                timeout=25,
            )
            r.raise_for_status()
            data = r.json()

        results = []
        for rate in data.get("output", {}).get("rateReplyDetails", []):
            svc_type   = rate.get("serviceType", "")
            svc_name   = "FedEx " + FEDEX_SERVICES.get(svc_type, rate.get("serviceName", svc_type))
            rated      = rate.get("ratedShipmentDetails", [])
            if not rated:
                continue

            detail     = rated[0]
            total      = float(detail.get("totalNetCharge", 0))
            rate_detail = detail.get("shipmentRateDetail", {})
            freight    = float(rate_detail.get("totalBaseCharge", 0))
            currency   = rate_detail.get("currency", "USD")

            fuel = 0.0
            accessorials = 0.0
            for sc in rate_detail.get("surCharges", []):
                sc_type = sc.get("type", "")
                # amount may be nested dict or flat
                amt_raw = sc.get("amount", 0)
                amt = float(amt_raw.get("amount", 0) if isinstance(amt_raw, dict) else amt_raw)
                if sc_type == "FUEL":
                    fuel += amt
                else:
                    accessorials += amt

            ops_detail = rate.get("operationalDetail", {})
            delivery_date = ops_detail.get("deliveryDate")
            transit_raw   = ops_detail.get("transitTime", "")
            transit_days  = FEDEX_TRANSIT_MAP.get(transit_raw) if transit_raw else None

            results.append(RateResult(
                carrier="FedEx",
                service_name=svc_name,
                service_code=svc_type,
                total_charge=round(total, 2),
                freight_charge=round(freight, 2),
                fuel_surcharge=round(fuel, 2),
                accessorial_charges=round(accessorials, 2),
                currency=currency,
                estimated_delivery=delivery_date,
                transit_days=transit_days,
            ))

        return results or [RateResult(
            carrier="FedEx", service_name="No rates returned", service_code="",
            total_charge=0, freight_charge=0, fuel_surcharge=0,
            accessorial_charges=0, currency="USD",
            error="FedEx returned no rates for this shipment",
        )]

    except httpx.HTTPStatusError as exc:
        return [RateResult(
            carrier="FedEx", service_name="Error", service_code="",
            total_charge=0, freight_charge=0, fuel_surcharge=0,
            accessorial_charges=0, currency="USD",
            error=f"HTTP {exc.response.status_code}: {exc.response.text[:300]}",
        )]
    except Exception as exc:
        return [RateResult(
            carrier="FedEx", service_name="Error", service_code="",
            total_charge=0, freight_charge=0, fuel_surcharge=0,
            accessorial_charges=0, currency="USD",
            error=str(exc),
        )]


# ─── DHL ──────────────────────────────────────────────────────────────────────

async def get_dhl_rates(req: RateRequest) -> List[RateResult]:
    if not req.credentials.dhl_api_key:
        return [RateResult(
            carrier="DHL", service_name="—", service_code="",
            total_charge=0, freight_charge=0, fuel_surcharge=0,
            accessorial_charges=0, currency="USD",
            error="No DHL API key provided",
        )]
    try:
        creds_b64 = base64.b64encode(
            f"{req.credentials.dhl_api_key}:".encode()
        ).decode()

        weight_kg = round(to_kg(req.weight, req.weight_unit), 3)
        length_cm = round(to_cm(req.length, req.dim_unit), 1)
        width_cm  = round(to_cm(req.width,  req.dim_unit), 1)
        height_cm = round(to_cm(req.height, req.dim_unit), 1)
        has_dims  = length_cm > 0 and width_cm > 0 and height_cm > 0

        params = {
            "originCountryCode":      req.origin_country,
            "originPostalCode":       req.origin_zip,
            "destinationCountryCode": req.dest_country,
            "destinationPostalCode":  req.dest_zip,
            "weight":                 weight_kg,
            **({"length": length_cm, "width": width_cm, "height": height_cm} if has_dims else {}),
            "plannedShippingDateAndTime": f"{req.ship_date}T12:00:00 GMT+00:00",
            "isCustomsDeclarable":    "false",
            "unitOfMeasurement":      "metric",
            "nextBusinessDay":        "false",
        }

        if req.residential:
            params["strictValidation"] = "false"

        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://express.api.dhl.com/mydhlapi/rates",
                headers={
                    "Authorization": f"Basic {creds_b64}",
                    "Content-Type": "application/json",
                },
                params=params,
                timeout=25,
            )
            r.raise_for_status()
            data = r.json()

        results = []
        for product in data.get("products", []):
            svc_name = "DHL " + product.get("productName", "Express")
            svc_code = product.get("productCode", "")

            # Total price — prefer USD, fall back to first currency found
            total = 0.0
            currency = "USD"
            for price in product.get("totalPrice", []):
                total    = float(price.get("price", 0))
                currency = price.get("priceCurrency", "USD")
                if currency == "USD":
                    break

            # Breakdown
            freight = 0.0
            fuel    = 0.0
            access  = 0.0
            for b in product.get("totalPriceBreakdown", []):
                b_type = b.get("priceType", "").upper()
                amt    = float(b.get("price", 0))
                if b_type in ("TRANSPORTATION", "FREIGHT", "BASE_CHARGE"):
                    freight += amt
                elif "FUEL" in b_type:
                    fuel += amt
                else:
                    access += amt

            # Fallback split if no breakdown provided
            if freight == 0 and total > 0:
                freight = round(total * 0.75, 2)
                fuel    = round(total * 0.15, 2)
                access  = round(total - freight - fuel, 2)

            # Delivery date
            caps = product.get("deliveryCapabilities", {})
            delivery_raw  = caps.get("estimatedDeliveryDateAndTime", "")
            delivery_date = delivery_raw[:10] if delivery_raw else None

            results.append(RateResult(
                carrier="DHL",
                service_name=svc_name,
                service_code=svc_code,
                total_charge=round(total, 2),
                freight_charge=round(freight, 2),
                fuel_surcharge=round(fuel, 2),
                accessorial_charges=round(access, 2),
                currency=currency,
                estimated_delivery=delivery_date,
            ))

        return results or [RateResult(
            carrier="DHL", service_name="No rates returned", service_code="",
            total_charge=0, freight_charge=0, fuel_surcharge=0,
            accessorial_charges=0, currency="USD",
            error="DHL returned no rates for this shipment",
        )]

    except httpx.HTTPStatusError as exc:
        return [RateResult(
            carrier="DHL", service_name="Error", service_code="",
            total_charge=0, freight_charge=0, fuel_surcharge=0,
            accessorial_charges=0, currency="USD",
            error=f"HTTP {exc.response.status_code}: {exc.response.text[:300]}",
        )]
    except Exception as exc:
        return [RateResult(
            carrier="DHL", service_name="Error", service_code="",
            total_charge=0, freight_charge=0, fuel_surcharge=0,
            accessorial_charges=0, currency="USD",
            error=str(exc),
        )]


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/api/rates", response_model=List[RateResult])
async def get_rates(req: RateRequest):
    """
    Fetch rates from UPS, FedEx, and DHL in parallel.
    Returns a flat list of RateResult objects sorted by total_charge.
    """
    ups_results, fedex_results, dhl_results = await asyncio.gather(
        get_ups_rates(req),
        get_fedex_rates(req),
        get_dhl_rates(req),
    )

    all_results = ups_results + fedex_results + dhl_results

    # Sort by total_charge ascending; errors go to bottom
    all_results.sort(
        key=lambda r: (r.error is not None, r.total_charge)
    )

    return all_results
