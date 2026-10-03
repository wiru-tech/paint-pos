import random
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Profile
from catalog.models import Brand, Category, ColorFormula, ColorFormulaLine, Pigment, Product
from core.models import Branch
from customers.models import Customer, SavedFormula
from inventory.models import PigmentStockLevel, StockLevel
from sales.models import Payment, Sale, SaleItem

User = get_user_model()


class Command(BaseCommand):
    help = "Seed the database with demo branches, catalog, stock, customers and sales history."

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(42)

        branches = self._seed_branches()
        self._seed_users(branches)
        categories = self._seed_categories()
        brands = self._seed_brands()
        products = self._seed_products(categories, brands)
        pigments = self._seed_pigments()
        self._seed_stock(branches, products)
        self._seed_warehouses(products, pigments)
        formulas = self._seed_color_formulas(products, pigments)
        self._seed_color_menu(products, pigments, formulas)
        customers = self._seed_customers(brands)
        self._seed_saved_formulas(customers, formulas)
        self._seed_sales(branches, products, customers, formulas)

        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully."))

    def _seed_branches(self):
        data = [
            ("Downtown Branch", "DTN", "120 Main St"),
            ("North Hub", "NHB", "48 Industrial Ave"),
            ("Industrial Park", "IND", "900 Freight Rd"),
            ("Westside", "WST", "12 Sunset Blvd"),
            ("East Depot", "EST", "77 Harbor Way"),
        ]
        branches = {}
        for name, code, address in data:
            branch, _ = Branch.objects.get_or_create(code=code, defaults={"name": name, "address": address})
            branches[code] = branch
        self.stdout.write(f"Branches: {len(branches)}")
        return branches

    def _seed_warehouses(self, products, pigments):
        """A central warehouse, kept out of ``branches`` so it never gets a POS
        login, a dashboard/report entry, or a staff assignment — only stock and
        the ability to transfer that stock out to a retail branch."""
        warehouse, created = Branch.objects.get_or_create(
            code="WH1",
            defaults={"name": "Central Warehouse", "address": "500 Distribution Way", "is_warehouse": True},
        )
        if not created and not warehouse.is_warehouse:
            warehouse.is_warehouse = True
            warehouse.save(update_fields=["is_warehouse"])

        stock_created = 0
        for product in products.values():
            _, was_created = StockLevel.objects.get_or_create(
                branch=warehouse, product=product,
                defaults={
                    "quantity": random.randint(200, 600),
                    "reorder_threshold": product.reorder_threshold * 3,
                },
            )
            stock_created += was_created

        pigment_created = 0
        for pigment in pigments.values():
            _, was_created = PigmentStockLevel.objects.get_or_create(
                branch=warehouse, pigment=pigment,
                defaults={"volume_ml": Decimal(random.randint(2000, 8000))},
            )
            pigment_created += was_created

        self.stdout.write(
            f"Warehouses: 1 ({warehouse.name}), stock lines: {stock_created}, pigment lines: {pigment_created}"
        )
        return warehouse

    def _seed_users(self, branches):
        downtown = branches["DTN"]
        specs = [
            # (username, password, is_staff, is_superuser, role, branch)
            ("admin", "admin12345", True, True, Profile.ROLE_MANAGER, downtown),
            ("manager1", "chromapos123", True, False, Profile.ROLE_MANAGER, downtown),
            ("cashier1", "chromapos123", True, False, Profile.ROLE_CASHIER, downtown),
        ]
        # One manager + one cashier per non-Downtown branch, e.g. manager_nhb / cashier_nhb.
        for code, branch in branches.items():
            if code == "DTN":
                continue
            suffix = code.lower()
            specs += [
                (f"manager_{suffix}", "chromapos123", True, False, Profile.ROLE_MANAGER, branch),
                (f"cashier_{suffix}", "chromapos123", True, False, Profile.ROLE_CASHIER, branch),
            ]

        for username, password, is_staff, is_superuser, role, branch in specs:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"is_staff": is_staff, "is_superuser": is_superuser},
            )
            if created:
                user.set_password(password)
                user.save()
            # update_or_create: the post_save signal on User already created a
            # blank Profile (role=cashier, branch=None) before we get here.
            Profile.objects.update_or_create(user=user, defaults={"branch": branch, "role": role})
        self.stdout.write("Users: admin/admin12345, manager1/chromapos123, cashier1/chromapos123")

    def _seed_categories(self):
        names = ["Interior Paint", "Exterior Paint", "Tinting Supplies", "Tools & Equipment"]
        cats = {}
        for name in names:
            cat, _ = Category.objects.get_or_create(name=name)
            cats[name] = cat
        return cats

    def _seed_brands(self):
        names = ["AeroCoat", "ProLine", "WeatherShield", "ChromaPro"]
        brands = {}
        for name in names:
            brand, _ = Brand.objects.get_or_create(name=name)
            brands[name] = brand
        return brands

    def _seed_products(self, categories, brands):
        interior = categories["Interior Paint"]
        exterior = categories["Exterior Paint"]
        tinting = categories["Tinting Supplies"]
        tools = categories["Tools & Equipment"]
        aerocoat = brands["AeroCoat"]
        proline = brands["ProLine"]
        weathershield = brands["WeatherShield"]
        chromapro = brands["ChromaPro"]

        # (sku, name, category, brand, unit_label, price, cost, is_tintable, reorder, base_type)
        specs = [
            ("PRM-1004-1G", "Premium Matte Base 1 (Gallon)", interior, aerocoat, "1 Gal", "32.00", "19.50", True, 20, "Pastel Base"),
            ("PRM-1005-1Q", "Premium Matte Base 2 (Quart)", interior, aerocoat, "1 Qt", "12.00", "7.40", True, 20, "Pastel Base"),
            ("AERO-INT-PREM", "AeroCoat Premium Interior", interior, aerocoat, "1 Gal", "49.00", "31.00", True, 15, "Deep Base"),
            ("EXT-5002-5G", "WeatherShield Satin (5 Gal)", exterior, weathershield, "5 Gal", "145.00", "98.00", True, 10, "Exterior Deep Base"),
            ("84920-EXT-4L", "Premium Exterior Acrylic", exterior, aerocoat, "4L", "59.00", "38.50", True, 10, "Exterior Neutral Base"),
            ("PROL-EXT-SHIELD", "ProLine Exterior Shield", exterior, proline, "1 Gal", "39.00", "27.00", True, 15, "Neutral Base"),
            ("TINT-B-001", "Colorant: Lamp Black (32oz)", tinting, chromapro, "32oz", "18.50", "11.00", False, 5, ""),
            ("TINT-C-002", "Colorant: Yellow Oxide (32oz)", tinting, chromapro, "32oz", "18.50", "11.00", False, 5, ""),
            ("TINT-E-003", "Colorant: Phthalo Blue (32oz)", tinting, chromapro, "32oz", "22.00", "14.25", False, 5, ""),
            ("TINT-KX-004", "Colorant: Titanium White (32oz)", tinting, chromapro, "32oz", "15.00", "8.60", False, 5, ""),
            ("TINT-TG-005", "Colorant: Thalo Green (32oz)", tinting, chromapro, "32oz", "21.00", "13.80", False, 5, ""),
            ("11200-RLL", 'Pro Roller Set 9"', tools, chromapro, "Set", "24.95", "15.20", False, 10, ""),
            ("BRUSH-3IN", 'Angled Sash Brush 3"', tools, chromapro, "Each", "9.99", "5.75", False, 10, ""),
            ("TAPE-2IN", 'Painter\'s Tape 2"', tools, chromapro, "Roll", "6.49", "3.90", False, 20, ""),
            ("DROP-9X12", "Canvas Drop Cloth 9x12", tools, chromapro, "Each", "14.99", "9.10", False, 10, ""),
        ]
        products = {}
        for sku, name, category, brand, unit_label, price, cost, is_tintable, reorder, base_type in specs:
            product, created = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "category": category,
                    "brand": brand,
                    "unit_label": unit_label,
                    "unit_price": Decimal(price),
                    "cost_price": Decimal(cost),
                    "is_tintable": is_tintable,
                    "reorder_threshold": reorder,
                    "base_type": base_type,
                },
            )
            # Products seeded before cost tracking existed have a 0 cost, which
            # would read as 100% margin in Reports. Backfill those.
            if not created and not product.cost_price:
                product.cost_price = Decimal(cost)
                product.save(update_fields=["cost_price"])
            products[sku] = product
        self.stdout.write(f"Products: {len(products)}")
        return products

    def _seed_pigments(self):
        specs = [
            ("B", "Lamp Black", "#000000", "0.4200"),
            ("C", "Yellow Oxide", "#E5D040", "0.3500"),
            ("E", "Phthalo Blue", "#0055A4", "0.5000"),
            ("KX", "Titanium White", "#FFFFFF", "0.1800"),
            ("TG", "Thalo Green", "#0B6E4F", "0.4800"),
        ]
        pigments = {}
        for code, name, hex_color, cost in specs:
            pigment, _ = Pigment.objects.get_or_create(
                code=code, defaults={"name": name, "hex_color": hex_color, "cost_per_ml": Decimal(cost)}
            )
            pigments[code] = pigment
        self.stdout.write(f"Pigments: {len(pigments)}")
        return pigments

    def _seed_stock(self, branches, products):
        count = 0
        for product in products.values():
            for branch in branches.values():
                _, created = StockLevel.objects.get_or_create(
                    branch=branch,
                    product=product,
                    defaults={
                        "quantity": random.randint(0, 180),
                        "reorder_threshold": product.reorder_threshold,
                    },
                )
                count += created
        self.stdout.write(f"Stock levels created: {count}")

    def _seed_color_formulas(self, products, pigments):
        formulas = {}

        ocean_mist, created = ColorFormula.objects.get_or_create(
            name="Ocean Mist",
            defaults={
                "hex_color": "#91BED2",
                "r": 145, "g": 190, "b": 210,
                "base_product": products["84920-EXT-4L"],
                "base_size": ColorFormula.SIZE_4L,
                "finish": "",
            },
        )
        if created:
            ColorFormulaLine.objects.bulk_create([
                ColorFormulaLine(formula=ocean_mist, pigment=pigments["B"], shots=Decimal("1.25"), volume_ml=Decimal("12.0")),
                ColorFormulaLine(formula=ocean_mist, pigment=pigments["C"], shots=Decimal("0.50"), volume_ml=Decimal("4.8")),
                ColorFormulaLine(formula=ocean_mist, pigment=pigments["E"], shots=Decimal("8.50"), volume_ml=Decimal("81.6")),
                ColorFormulaLine(formula=ocean_mist, pigment=pigments["KX"], shots=Decimal("1.67"), volume_ml=Decimal("16.1")),
            ])
        formulas["Ocean Mist"] = ocean_mist

        deep_forest, created = ColorFormula.objects.get_or_create(
            name="Deep Forest Study",
            defaults={
                "hex_color": "#2D4A3E",
                "r": 45, "g": 74, "b": 62,
                "base_product": products["AERO-INT-PREM"],
                "base_size": ColorFormula.SIZE_4L,
                "finish": "Matte",
            },
        )
        if created:
            ColorFormulaLine.objects.bulk_create([
                ColorFormulaLine(formula=deep_forest, pigment=pigments["B"], shots=Decimal("12.00"), volume_ml=Decimal("18.5")),
                ColorFormulaLine(formula=deep_forest, pigment=pigments["C"], shots=Decimal("4.10"), volume_ml=Decimal("6.3")),
                ColorFormulaLine(formula=deep_forest, pigment=pigments["TG"], shots=Decimal("1.20"), volume_ml=Decimal("1.8")),
            ])
        formulas["Deep Forest Study"] = deep_forest

        lobby_sand, created = ColorFormula.objects.get_or_create(
            name="Lobby Warm Sand",
            defaults={
                "hex_color": "#E8DCC4",
                "r": 232, "g": 220, "b": 196,
                "base_product": products["AERO-INT-PREM"],
                "base_size": ColorFormula.SIZE_4L,
                "finish": "Eggshell",
            },
        )
        if created:
            ColorFormulaLine.objects.bulk_create([
                ColorFormulaLine(formula=lobby_sand, pigment=pigments["KX"], shots=Decimal("20.00"), volume_ml=Decimal("30.5")),
                ColorFormulaLine(formula=lobby_sand, pigment=pigments["C"], shots=Decimal("3.00"), volume_ml=Decimal("4.6")),
            ])
        formulas["Lobby Warm Sand"] = lobby_sand

        navajo_white, created = ColorFormula.objects.get_or_create(
            name="Navajo White",
            defaults={
                "hex_color": "#F5F5F5",
                "r": 245, "g": 245, "b": 245,
                "base_product": products["PROL-EXT-SHIELD"],
                "base_size": ColorFormula.SIZE_4L,
                "finish": "Satin",
            },
        )
        if created:
            ColorFormulaLine.objects.bulk_create([
                ColorFormulaLine(formula=navajo_white, pigment=pigments["KX"], shots=Decimal("25.00"), volume_ml=Decimal("38.0")),
            ])
        formulas["Navajo White"] = navajo_white

        self.stdout.write(f"Color formulas: {len(formulas)}")
        return formulas

    def _seed_color_menu(self, products, pigments, formulas):
        """Publish a handful of existing formulas as pre-approved Color Menu
        shades, plus one pastel that isn't in the seeded checkout history."""
        pastel_mint, created = ColorFormula.objects.get_or_create(
            name="Pastel Mint",
            defaults={
                "hex_color": "#DCEFE3",
                "r": 220, "g": 239, "b": 227,
                "base_product": products["PRM-1004-1G"],
                "base_size": ColorFormula.SIZE_1L,
                "finish": "Eggshell",
            },
        )
        if created:
            ColorFormulaLine.objects.bulk_create([
                ColorFormulaLine(formula=pastel_mint, pigment=pigments["KX"], shots=Decimal("14.00"), volume_ml=Decimal("21.0")),
                ColorFormulaLine(formula=pastel_mint, pigment=pigments["TG"], shots=Decimal("0.80"), volume_ml=Decimal("1.2")),
                ColorFormulaLine(formula=pastel_mint, pigment=pigments["C"], shots=Decimal("0.30"), volume_ml=Decimal("0.5")),
            ])

        shade_specs = [
            ("Pastel Mint", "SW-PASTEL-01", ColorFormula.CATEGORY_PASTELS, pastel_mint),
            ("Navajo White", "SW-6126", ColorFormula.CATEGORY_NEUTRALS, formulas["Navajo White"]),
            ("Lobby Warm Sand", "RAL 1015", ColorFormula.CATEGORY_EARTH_TONES, formulas["Lobby Warm Sand"]),
            ("Deep Forest Study", "SW-7005", ColorFormula.CATEGORY_BOLD_ACCENTS, formulas["Deep Forest Study"]),
            ("Ocean Mist", "RAL 9010", ColorFormula.CATEGORY_EXTERIOR_SHADES, formulas["Ocean Mist"]),
        ]
        published = 0
        for _, code, category, formula in shade_specs:
            ColorFormula.objects.filter(pk=formula.pk).update(
                code=code, shade_category=category, is_catalog_shade=True,
            )
            published += 1

        # A handful more per category so the Color Menu grid actually reads
        # as a grid (rows x columns) instead of one card per section.
        extra_specs = [
            ("Blush Whisper", "SW-PASTEL-02", ColorFormula.CATEGORY_PASTELS, "F7DCE0", "PRM-1004-1G", ColorFormula.SIZE_1L, "Eggshell"),
            ("Powder Sky", "SW-PASTEL-03", ColorFormula.CATEGORY_PASTELS, "DCEAF7", "PRM-1005-1Q", ColorFormula.SIZE_1L, "Matte"),
            ("Buttercream", "SW-PASTEL-04", ColorFormula.CATEGORY_PASTELS, "FBF3D9", "PRM-1004-1G", ColorFormula.SIZE_1L, "Satin"),
            ("Greige Cloud", "SW-6127", ColorFormula.CATEGORY_NEUTRALS, "D9D3C7", "PROL-EXT-SHIELD", ColorFormula.SIZE_4L, "Matte"),
            ("Warm Linen", "SW-6128", ColorFormula.CATEGORY_NEUTRALS, "E8E1D3", "84920-EXT-4L", ColorFormula.SIZE_4L, "Eggshell"),
            ("Stone Grey", "SW-6129", ColorFormula.CATEGORY_NEUTRALS, "C9C6BE", "PROL-EXT-SHIELD", ColorFormula.SIZE_4L, "Satin"),
            ("Terracotta Dust", "RAL 1016", ColorFormula.CATEGORY_EARTH_TONES, "C97B4A", "AERO-INT-PREM", ColorFormula.SIZE_4L, "Matte"),
            ("Clay Ridge", "RAL 1017", ColorFormula.CATEGORY_EARTH_TONES, "A9673E", "84920-EXT-4L", ColorFormula.SIZE_4L, "Eggshell"),
            ("Desert Sage", "RAL 1018", ColorFormula.CATEGORY_EARTH_TONES, "A6A480", "PROL-EXT-SHIELD", ColorFormula.SIZE_4L, "Satin"),
            ("Crimson Ember", "SW-7006", ColorFormula.CATEGORY_BOLD_ACCENTS, "8C1D26", "AERO-INT-PREM", ColorFormula.SIZE_1L, "Semi-Gloss"),
            ("Cobalt Surge", "SW-7007", ColorFormula.CATEGORY_BOLD_ACCENTS, "1B3F8C", "AERO-INT-PREM", ColorFormula.SIZE_1L, "Matte"),
            ("Sunburst Gold", "SW-7008", ColorFormula.CATEGORY_BOLD_ACCENTS, "D9A441", "AERO-INT-PREM", ColorFormula.SIZE_1L, "Gloss"),
            ("Storm Slate", "RAL 9011", ColorFormula.CATEGORY_EXTERIOR_SHADES, "5B6B73", "EXT-5002-5G", ColorFormula.SIZE_20L, "Satin"),
            ("Coastal Fog", "RAL 9012", ColorFormula.CATEGORY_EXTERIOR_SHADES, "B9C4C2", "84920-EXT-4L", ColorFormula.SIZE_4L, "Matte"),
            ("Harbor Navy", "RAL 9013", ColorFormula.CATEGORY_EXTERIOR_SHADES, "2E3F52", "EXT-5002-5G", ColorFormula.SIZE_20L, "Semi-Gloss"),
        ]
        for name, code, category, hex_color, product_sku, base_size, finish in extra_specs:
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            _, created_extra = ColorFormula.objects.get_or_create(
                name=name,
                defaults={
                    "hex_color": f"#{hex_color}", "r": r, "g": g, "b": b,
                    "base_product": products[product_sku], "base_size": base_size, "finish": finish,
                    "code": code, "shade_category": category, "is_catalog_shade": True,
                },
            )
            if created_extra:
                published += 1
        self.stdout.write(f"Color Menu shades published: {published}")

    def _seed_customers(self, brands):
        specs = [
            (
                "Elena Jenkins", "(555) 019-2834", "elena.jenkins@example.com", True, "150.00", brands["AeroCoat"],
                "Prefers AeroCoat brand for interior jobs.\n\n"
                "Always uses Matte finish in living areas, Eggshell in hallways.\n\n"
                "Requires physical swatches printed for large orders (>10 Gal).",
            ),
            ("Marcus Reed", "(555) 244-7710", "marcus.reed@example.com", False, "0.00", brands["ProLine"], ""),
            ("Priya Nair", "(555) 388-1200", "priya.nair@example.com", True, "40.00", brands["WeatherShield"], ""),
        ]
        customers = {}
        for name, phone, email, is_pro, credit, brand, notes in specs:
            customer, _ = Customer.objects.get_or_create(
                name=name,
                defaults={
                    "phone": phone, "email": email, "is_pro": is_pro,
                    "store_credit": Decimal(credit), "favorite_brand": brand, "notes": notes,
                },
            )
            customers[name] = customer
        self.stdout.write(f"Customers: {len(customers)}")
        return customers

    def _seed_saved_formulas(self, customers, formulas):
        specs = [
            ("CUS-892-A", customers["Elena Jenkins"], formulas["Deep Forest Study"], SavedFormula.FINISH_MATTE),
            ("CUS-441-B", customers["Elena Jenkins"], formulas["Lobby Warm Sand"], SavedFormula.FINISH_EGGSHELL),
        ]
        for ref, customer, formula, finish in specs:
            SavedFormula.objects.get_or_create(
                reference_code=ref,
                defaults={"customer": customer, "color_formula": formula, "finish": finish},
            )

    def _seed_sales(self, branches, products, customers, formulas):
        downtown = branches["DTN"]
        cashier = User.objects.get(username="cashier1")
        elena = customers["Elena Jenkins"]

        specs = [
            (
                "INV-9923", datetime(2023, 10, 12, 14, 30, tzinfo=dt_timezone.utc),
                [("AeroCoat Premium Interior — Deep Forest Study (Matte)", 5, "49.00", formulas["Deep Forest Study"], products["AERO-INT-PREM"])],
                "245.00",
            ),
            (
                "INV-8812", datetime(2023, 9, 4, 11, 5, tzinfo=dt_timezone.utc),
                [("ProLine Exterior Shield — Navajo White (Satin)", 10, "39.00", formulas["Navajo White"], products["PROL-EXT-SHIELD"])],
                "390.00",
            ),
            (
                "INV-7433", datetime(2023, 8, 22, 16, 15, tzinfo=dt_timezone.utc),
                [("AeroCoat Premium Interior — Lobby Warm Sand (Eggshell)", 2, "52.75", formulas["Lobby Warm Sand"], products["AERO-INT-PREM"])],
                "105.50",
            ),
        ]

        for invoice_number, created_at, items, total in specs:
            if Sale.objects.filter(invoice_number=invoice_number).exists():
                continue
            sale = Sale.objects.create(
                invoice_number=invoice_number,
                branch=downtown,
                cashier=cashier,
                customer=elena,
                status=Sale.STATUS_COMPLETED,
                created_at=created_at,
                completed_at=created_at,
            )
            for description, qty, unit_price, formula, product in items:
                SaleItem.objects.create(
                    sale=sale,
                    product=product,
                    color_formula=formula,
                    description=description,
                    quantity=Decimal(qty),
                    unit_price=Decimal(unit_price),
                    unit_cost=product.cost_price if product else Decimal("0"),
                )
            sale.subtotal = Decimal(total)
            sale.tax = Decimal("0.00")
            sale.total = Decimal(total)
            sale.save(update_fields=["subtotal", "tax", "total"])
            Payment.objects.create(sale=sale, method=Payment.METHOD_CARD, amount=Decimal(total))

        self.stdout.write("Sales history seeded for Elena Jenkins (3 invoices).")
