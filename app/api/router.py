from fastapi import APIRouter

from app.api.routers import address, admin, cart, category, favorite, order, payment, product, refund, seller, support

api_router = APIRouter()
api_router.include_router(product.router)
api_router.include_router(category.router)
api_router.include_router(favorite.router)
api_router.include_router(cart.router)
api_router.include_router(order.router)
api_router.include_router(payment.router)
api_router.include_router(refund.router)
api_router.include_router(address.router)
api_router.include_router(admin.router)
api_router.include_router(seller.router)
api_router.include_router(support.router)
