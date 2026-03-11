from django.test import TestCase
from rest_framework.test import APIClient

from .models import Product


class ProductPaginationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_products_list_is_paginated(self):
        for i in range(15):
            Product.objects.create(name=f"Product {i:02}", slug=f"product-{i:02}", is_active=True)

        response = self.client.get("/api/catalog/products/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["count"], 15)
        self.assertEqual(len(response.data["results"]), 12)

    def test_products_page_size_query_param_is_supported(self):
        for i in range(7):
            Product.objects.create(name=f"Product {i:02}", slug=f"product-size-{i:02}", is_active=True)

        response = self.client.get("/api/catalog/products/?page_size=5")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 5)
