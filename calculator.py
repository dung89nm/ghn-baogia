#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import math
from datetime import datetime

try:
    import google.generativeai as genai
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox
    import threading
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False

class ShippingCalculator:
    """
    Lớp tính toán cước vận chuyển linh hoạt, tối thiểu cần quãng đường và trọng lượng.
    Cấu hình được nhúng trực tiếp trong mã.
    """

    DEFAULT_CONFIG = {
        "km_coefficients": [
            [0, 0.35], [50, 0.35], [100, 0.4], [150, 0.45], [200, 0.5], [250, 0.55],
            [300, 0.6], [350, 0.65], [400, 0.7], [450, 0.75], [500, 0.8], [550, 0.825],
            [600, 0.85], [650, 0.875], [700, 0.9], [750, 0.925], [800, 0.95], [850, 0.975],
            [900, 1.0], [950, 1.025], [1000, 1.05], [1100, 1.075], [1200, 1.1], [1300, 1.125],
            [1400, 1.15], [1500, 1.175], [1600, 1.2], [1700, 1.225], [1800, 1.25], [1900, 1.275],
            [2000, 1.3], [2100, 1.325], [2200, 1.35], [2300, 1.375], [2400, 1.4], [2500, 1.6]
        ],
        "zone_coefficients": {
            "Vùng 1": 1.4,
            "Vùng 5": 1.3,
            "Vùng còn lại": 1.0,
            "Vùng huyện đảo": 1.5
        },
        "goods_coefficients": {
            "Hàng trần VLXD": 0.8,
            "Hàng dễ vỡ": 1.5,
            "Hàng tiêu dùng": 1.0,
            "Hàng đông lạnh": 1.5,
            "Hàng hóa chất": 1.5,
            "Hàng đóng hộp tiêu dùng": 1.0,
            "Lúa thóc": 0.65
        },
        "vehicle_coefficients": {
            "Tải": 1.0,
            "Đầu kéo": 1.25,
            "Mooc sàn": 1.5,
            "Fooc": 2.25
        },
        "size_coefficients": [
            [0, 1.0], [200, 1.2], [300, 1.3], [400, 1.4], [600, 1.5], [800, 1.8], [1100, 2.0]
        ],
        "constants": {
            "full_vehicle_rate": 4076.05,
            "delivery_vinh_base": 5445000,
            "delivery_vinh_rate": 0.18,
            "vol_weight_factor": 6000
        },
        "zone_mapping": {
            "Hà Nội": "Vùng 1",
            "TP HCM": "Vùng 1",
            "Hải Phòng": "Vùng 1",
            "Đà Nẵng": "Vùng 5",
            "Cần Thơ": "Vùng 5",
            "Phú Quốc": "Vùng huyện đảo",
            "Côn Đảo": "Vùng huyện đảo",
            "Lý Sơn": "Vùng huyện đảo",
            "Nghệ An": "Vùng còn lại",
            "Thái Hòa": "Vùng còn lại",
            "Thanh Hóa": "Vùng còn lại",
            "Bắc Giang": "Vùng còn lại",
            "Bình Dương": "Vùng còn lại"
        }
    }

    def __init__(self):
        """
        Khởi tạo máy tính cước vận chuyển với cấu hình nhúng.
        """
        self.config = self.DEFAULT_CONFIG

    def get_km_coefficient(self, distance):
        """Lấy hệ số KM dựa trên khoảng cách."""
        coeffs = sorted(self.config["km_coefficients"], key=lambda x: x[0])
        km_coef = coeffs[0][1]
        for km_threshold, coef in coeffs:
            if distance >= km_threshold:
                km_coef = coef
            else:
                break
        return km_coef

    def get_zone_coefficient(self, zone_name):
        """Lấy hệ số vùng dựa trên tên vùng."""
        return self.config["zone_coefficients"].get(zone_name, 1.0)

    def get_goods_coefficient(self, goods_type):
        """Lấy hệ số hàng hóa."""
        return self.config["goods_coefficients"].get(goods_type, 1.0)

    def get_vehicle_coefficient(self, vehicle_type):
        """Lấy hệ số loại xe."""
        return self.config["vehicle_coefficients"].get(vehicle_type, 1.0)

    def get_size_coefficient(self, max_dimension):
        """Lấy hệ số kích thước."""
        max_dim = max_dimension or 0
        coeffs = sorted(self.config["size_coefficients"], key=lambda x: x[0])
        size_coef = coeffs[0][1]
        for size_threshold, coef in coeffs:
            if max_dim >= size_threshold:
                size_coef = coef
            else:
                break
        return size_coef

    def get_base_rate(self, chargeable_weight_kg):
        """Tính base_rate dựa trên trọng lượng tính cước (kg)."""
        if chargeable_weight_kg < 1000:
            return 5230.78  # Dưới 1 tấn
        elif 1000 <= chargeable_weight_kg < 3000:
            return 3130.78  # 1 tấn đến dưới 3 tấn
        elif 3000 <= chargeable_weight_kg < 10000:
            return 2180.78  # 3 tấn đến dưới 10 tấn
        else:
            return 1200.78  # Từ 10 tấn trở lên

    def calculate_weight_from_dimensions(self, length, width, height, factor=6000):
        """Tính trọng lượng quy đổi từ kích thước (cm)."""
        if length is None or width is None or height is None:
            return 0
        try:
            l = float(length)
            w = float(width)
            h = float(height)
            if factor <= 0:
                factor = 6000
            return (l * w * h) / factor
        except (ValueError, TypeError):
            return 0

    def get_zone_name_from_loc(self, location_name):
        """Lấy tên vùng từ tên địa điểm."""
        if not location_name:
            return "Vùng còn lại"
        location_lower = location_name.lower().strip()
        zone_map = self.config.get("zone_mapping", {})
        for key, zone in zone_map.items():
            if key.lower() in location_lower:
                return zone
        return "Vùng còn lại"

    def calculate_shipping_rate(self, distance_km, actual_weight_kg, quantity=1,
                               vol_length_cm=None, vol_width_cm=None, vol_height_cm=None,
                               pickup_zone_name="Vùng còn lại", delivery_zone_name="Vùng còn lại",
                               delivery_point="", goods_type="Hàng đóng hộp tiêu dùng",
                               vehicle_type="Tải", proposed_coefficient=1.0):
        """
        Tính toán cước vận chuyển với base_rate dựa trên khoảng trọng lượng.
        """
        results = {"error": None}

        try:
            # Validate inputs
            distance = float(distance_km)
            actual_weight = float(actual_weight_kg) if actual_weight_kg is not None else 0
            qty = int(quantity) if quantity is not None else 1
            proposed_coef = float(proposed_coefficient) if proposed_coefficient is not None else 1.0

            # Tính cân nặng quy đổi
            vol_weight = self.calculate_weight_from_dimensions(vol_length_cm, vol_width_cm, vol_height_cm,
                                                              self.config["constants"]["vol_weight_factor"])
            vol_weight_total = vol_weight * qty
            actual_weight_total = actual_weight * qty
            chargeable_weight = max(actual_weight_total, vol_weight_total) if vol_weight_total > 0 else actual_weight_total
            if chargeable_weight <= 0:
                chargeable_weight = 1

            results['chargeable_weight'] = chargeable_weight
            results['volumetric_weight'] = vol_weight_total
            results['actual_weight'] = actual_weight_total

            # Lấy hệ số
            km_coef = self.get_km_coefficient(distance)
            pickup_zone_coef = self.get_zone_coefficient(pickup_zone_name)
            delivery_zone_coef = self.get_zone_coefficient(delivery_zone_name)
            goods_coef = self.get_goods_coefficient(goods_type)
            vehicle_coef = self.get_vehicle_coefficient(vehicle_type)
            size_coef = self.get_size_coefficient(max([vol_length_cm or 0, vol_width_cm or 0, vol_height_cm or 0]))
            max_zone_coef = max(pickup_zone_coef, delivery_zone_coef)

            results['coefficients'] = {
                'km': km_coef,
                'zone': max_zone_coef,
                'goods': goods_coef,
                'vehicle': vehicle_coef,
                'size': size_coef,
                'proposed': proposed_coef
            }

            # Tính base_rate dựa trên trọng lượng
            base_rate = self.get_base_rate(chargeable_weight)

            # Tính cước tạm tính
            base_freight = chargeable_weight * km_coef * max_zone_coef * goods_coef * size_coef * proposed_coef * base_rate
            results['base_freight'] = base_freight

            # Tính phí giao tận nơi
            delivery_fee = 0
            if delivery_point and delivery_point.lower().strip() == "tp vinh":
                delivery_fee = self.config["constants"]["delivery_vinh_base"] * self.config["constants"]["delivery_vinh_rate"]
            results['delivery_fee'] = delivery_fee

            # Tổng tiền
            total_cost = base_freight + delivery_fee
            results['total_cost'] = total_cost

            # Giá xe ghép
            shared_vehicle_cost = base_freight * 0.9
            results['shared_vehicle_cost'] = shared_vehicle_cost

            # Giá nguyên xe
            full_vehicle_rate = self.config["constants"]["full_vehicle_rate"]
            full_vehicle_cost = chargeable_weight * km_coef * max_zone_coef * goods_coef * vehicle_coef * proposed_coef * full_vehicle_rate
            results['full_vehicle_cost'] = full_vehicle_cost

            # Giá báo khách
            results['customer_price'] = total_cost

            # Làm tròn các giá trị
            for key in ['base_freight', 'delivery_fee', 'total_cost', 'shared_vehicle_cost', 'full_vehicle_cost', 'customer_price']:
                results[key] = round(results[key])

        except (ValueError, TypeError) as e:
            results["error"] = f"Lỗi giá trị đầu vào: {e}"
        except KeyError as ke:
            results["error"] = f"Lỗi cấu hình: Thiếu khóa {ke} trong cấu hình nhúng"
        except Exception as e:
            results["error"] = f"Lỗi hệ thống: {e}"

        return results

    def format_price(self, price):
        """Định dạng giá tiền kiểu Việt Nam."""
        if isinstance(price, (int, float)):
            price_rounded = round(price)
            return f"{price_rounded:,.0f}".replace(",", ".")
        return str(price)

    def process_query(self, query, default_goods_type="Hàng đóng hộp tiêu dùng", default_vehicle_type="Tải"):
        """
        Xử lý yêu cầu từ chat, trích xuất thông tin và tính cước.
        """
        try:
            parsed_data = self.parse_user_query(query)
            distance = parsed_data.get('distance')
            actual_weight = parsed_data.get('weight')
            quantity = parsed_data.get('quantity', 1)
            length_cm = parsed_data.get('dimensions', {}).get('length')
            width_cm = parsed_data.get('dimensions', {}).get('width')
            height_cm = parsed_data.get('dimensions', {}).get('height')
            pickup_loc = parsed_data.get('from_location', "Vùng còn lại")
            delivery_loc = parsed_data.get('to_location', "Vùng còn lại")
            delivery_point = parsed_data.get('delivery_point', "")
            goods_type = parsed_data.get('goods_type', default_goods_type)
            vehicle_type = parsed_data.get('vehicle_type', default_vehicle_type)
            proposed_coefficient = parsed_data.get('proposed_coefficient', 1.0)

            if distance is None or actual_weight is None:
                return "Vui lòng cung cấp quãng đường (km) và trọng lượng (kg hoặc tấn)."

            pickup_zone = self.get_zone_name_from_loc(pickup_loc)
            delivery_zone = self.get_zone_name_from_loc(delivery_loc)

            result = self.calculate_shipping_rate(
                distance_km=distance,
                actual_weight_kg=actual_weight,
                quantity=quantity,
                vol_length_cm=length_cm,
                vol_width_cm=width_cm,
                vol_height_cm=height_cm,
                pickup_zone_name=pickup_zone,
                delivery_zone_name=delivery_zone,
                delivery_point=delivery_point,
                goods_type=goods_type,
                vehicle_type=vehicle_type,
                proposed_coefficient=proposed_coefficient
            )

            if result.get("error"):
                return f"Lỗi: {result['error']}"

            response = f"Báo giá vận chuyển từ {pickup_loc} (Vùng: {pickup_zone}) đến {delivery_loc} (Vùng: {delivery_zone}):\n\n"
            response += f"- Số lượng: {quantity}\n"
            if length_cm:
                response += f"- Kích thước: {length_cm}x{width_cm}x{height_cm} cm\n"
            response += f"- Trọng lượng thực: {actual_weight:.2f} kg\n"
            if result['volumetric_weight'] > 0:
                response += f"- Trọng lượng quy đổi: {result['volumetric_weight']:.2f} kg\n"
            response += f"- Trọng lượng tính cước: {result['chargeable_weight']:.2f} kg\n"
            response += f"- Khoảng cách: {distance} km\n"
            response += f"- Loại hàng: {goods_type}\n"
            response += f"- Loại xe: {vehicle_type}\n"
            response += f"- Hệ số đề xuất: {proposed_coefficient}\n\n"
            response += f"**Kết quả tính cước:**\n"
            response += f"- Cước tạm tính: {self.format_price(result['base_freight'])} VNĐ\n"
            response += f"- Phí giao tận nơi: {self.format_price(result['delivery_fee'])} VNĐ\n"
            response += f"- Tổng tiền: {self.format_price(result['total_cost'])} VNĐ\n"
            response += f"- Giá xe ghép: {self.format_price(result['shared_vehicle_cost'])} VNĐ\n"
            response += f"- Giá nguyên xe: {self.format_price(result['full_vehicle_cost'])} VNĐ\n"
            response += f"- Giá báo khách: {self.format_price(result['customer_price'])} VNĐ\n"

            return response

        except Exception as e:
            return f"Lỗi xử lý yêu cầu: {e}"

    def parse_user_query(self, query):
        """
        Phân tích yêu cầu người dùng với regex tối ưu.
        """
        result = {
            'from_location': None, 'to_location': None, 'delivery_point': None,
            'weight': None, 'dimensions': {'length': None, 'width': None, 'height': None},
            'quantity': 1, 'distance': None, 'goods_type': None, 'vehicle_type': None,
            'proposed_coefficient': 1.0, 'confidence': 0.0
        }
        query_lower = query.lower()

        # Tìm địa điểm
        from_pattern = r'(?:từ|chở từ|vận chuyển từ|đi từ)\s+([\w\s\d\.,/-]+?)\s*(?:đến|tới|về|$)'
        to_pattern = r'(?:đến|tới|về)\s+([\w\s\d\.,/-]+?)(?:,|\.|$|\n)'
        delivery_pattern = r'giao\s*(?:tận nơi|tới)?\s*([\w\s\d\.,/-]+?)(?:,|\.|$|\n)'
        from_match = re.search(from_pattern, query, re.IGNORECASE)
        to_match = re.search(to_pattern, query, re.IGNORECASE)
        delivery_match = re.search(delivery_pattern, query, re.IGNORECASE)
        if from_match:
            result['from_location'] = from_match.group(1).strip()
            result['confidence'] += 0.2
        if to_match:
            result['to_location'] = to_match.group(1).strip()
            result['confidence'] += 0.2
        if delivery_match:
            result['delivery_point'] = delivery_match.group(1).strip()
            result['confidence'] += 0.1

        # Tìm trọng lượng
        weight_pattern = r'(\d+(?:[.,]\d+)?)\s*(tấn|kg|kilogam|kilogram|cân)'
        weight_match = re.search(weight_pattern, query_lower)
        if weight_match:
            weight_value = float(weight_match.group(1).replace(',', '.'))
            unit = weight_match.group(2)
            if unit == 'tấn':
                weight_value *= 1000
            result['weight'] = weight_value
            result['confidence'] += 0.2

        # Tìm số lượng
        quantity_pattern = r'số kiện\s*[:=]?\s*(\d+)'
        quantity_match = re.search(quantity_pattern, query, re.IGNORECASE)
        if quantity_match:
            result['quantity'] = int(quantity_match.group(1))
            result['confidence'] += 0.1

        # Tìm kích thước
        dim_pattern = r'kích thước\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*[x*×]\s*(\d+(?:[.,]\d+)?)\s*[x*×]\s*(\d+(?:[.,]\d+)?)\s*(cm|centimet)?'
        dim_match = re.search(dim_pattern, query, re.IGNORECASE)
        if dim_match:
            result['dimensions'] = {
                'length': float(dim_match.group(1).replace(',', '.')),
                'width': float(dim_match.group(2).replace(',', '.')),
                'height': float(dim_match.group(3).replace(',', '.'))
            }
            result['confidence'] += 0.15

        # Tìm quãng đường
        distance_pattern = r'(\d+(?:[.,]\d+)?)\s*(km|kilomet|kilometer)'
        distance_match = re.search(distance_pattern, query_lower)
        if distance_match:
            result['distance'] = float(distance_match.group(1).replace(',', '.'))
            result['confidence'] += 0.2

        # Tìm loại hàng
        goods_pattern = r'loại hàng\s*[:=]?\s*([\w\s]+?)(?:,|\.|$|\n)'
        goods_match = re.search(goods_pattern, query, re.IGNORECASE)
        if goods_match:
            result['goods_type'] = goods_match.group(1).strip()
            result['confidence'] += 0.1

        # Tìm loại xe
        vehicle_pattern = r'loại xe\s*[:=]?\s*([\w\s]+?)(?:,|\.|$|\n)'
        vehicle_match = re.search(vehicle_pattern, query, re.IGNORECASE)
        if vehicle_match:
            result['vehicle_type'] = vehicle_match.group(1).strip()
            result['confidence'] += 0.1

        # Tìm hệ số đề xuất
        coef_pattern = r'hệ số đề xuất\s*[:=]?\s*(\d+(?:[.,]\d+)?)'
        coef_match = re.search(coef_pattern, query, re.IGNORECASE)
        if coef_match:
            result['proposed_coefficient'] = float(coef_match.group(1).replace(',', '.'))
            result['confidence'] += 0.1

        result['confidence'] = round(result['confidence'], 2)
        return result

if TKINTER_AVAILABLE:
    class ShippingAssistantApp:
        def __init__(self, root):
            self.root = root
            self.root.title("Trợ lý báo giá cước vận chuyển")
            root.geometry("1100x750")
            root.minsize(900, 650)

            self.calculator = ShippingCalculator()

            self.api_key = "AIzaSyAEiNHrsLS7r9xbzJ9HORwP2PAZAzwceGw"  # Thay bằng API Key của bạn
            self.model = None
            self.setup_ai()

            self.chat_history_list = []
            self.chat_history_file = f"chat_history_{datetime.now().strftime('%Y%m%d')}.json"

            self.create_ui()
            self.load_chat_history()

            now = datetime.now()
            welcome_message = f"Xin chào! ({now.strftime('%d/%m/%Y %H:%M:%S')}).\nTrợ lý báo giá cước vận chuyển sẵn sàng. Vui lòng nhập yêu cầu hoặc sử dụng tab 'Nhập liệu chi tiết'."
            self.add_message("assistant", welcome_message, save=False)

            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        def on_closing(self):
            self.save_chat_history()
            self.root.destroy()

        def setup_ai(self):
            if not GOOGLE_API_AVAILABLE:
                print("Thư viện google.generativeai chưa được cài đặt.")
                return
            if not self.api_key:
                print("API Key chưa được cung cấp.")
                return
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-1.5-flash-latest')
                print("Kết nối Google Generative AI thành công.")
            except Exception as e:
                error_msg = f"Lỗi khi thiết lập Google Generative AI: {str(e)}"
                print(error_msg)
                self.root.after(100, self.add_message, "error", error_msg, False)
                self.model = None

        def create_ui(self):
            style = ttk.Style()
            style.theme_use('clam')
            style.configure('.', font=('Arial', 10))
            style.configure('TButton', padding=5)
            style.configure('Accent.TButton', background='#0078D7', foreground='white')

            self.notebook = ttk.Notebook(self.root)
            self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            self.chat_frame = ttk.Frame(self.notebook, padding=5)
            self.notebook.add(self.chat_frame, text="Trò chuyện")
            self.input_frame = ttk.Frame(self.notebook, padding=5)
            self.notebook.add(self.input_frame, text="Nhập liệu chi tiết")
            self.help_frame = ttk.Frame(self.notebook, padding=5)
            self.notebook.add(self.help_frame, text="Trợ giúp")

            self.setup_chat_tab()
            self.setup_input_tab()
            self.setup_help_tab()

        def setup_chat_tab(self):
            self.chat_frame.rowconfigure(1, weight=1)
            self.chat_frame.columnconfigure(0, weight=1)

            chat_title = ttk.Label(self.chat_frame, text="Trò chuyện với Trợ lý", font=("Arial", 14, "bold"))
            chat_title.grid(row=0, column=0, pady=(5,10), sticky="w")

            chat_display_frame = ttk.Frame(self.chat_frame, relief=tk.SUNKEN, borderwidth=1)
            chat_display_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
            chat_display_frame.rowconfigure(0, weight=1)
            chat_display_frame.columnconfigure(0, weight=1)

            self.chat_display = scrolledtext.ScrolledText(chat_display_frame, wrap=tk.WORD, font=("Arial", 11),
                                                         state=tk.DISABLED, padx=5, pady=5, relief=tk.FLAT)
            self.chat_display.grid(row=0, column=0, sticky="nsew")
            self.chat_display.tag_config("user", foreground="#0000AA", font=("Arial", 11, "bold"))
            self.chat_display.tag_config("assistant", foreground="#007700")
            self.chat_display.tag_config("error", foreground="#CC0000", font=("Arial", 11, "italic"))
            self.chat_display.tag_config("timestamp", foreground="#555555", font=("Arial", 9))

            input_frame = ttk.Frame(self.chat_frame)
            input_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=(5,10))
            input_frame.columnconfigure(0, weight=1)

            self.chat_input = ttk.Entry(input_frame, font=("Arial", 11))
            self.chat_input.grid(row=0, column=0, sticky="ew", padx=(0, 5), ipady=4)
            self.chat_input.bind("<Return>", self.send_message)

            send_button = ttk.Button(input_frame, text="Gửi", command=self.send_message, style='Accent.TButton')
            send_button.grid(row=0, column=1, padx=(0, 5))

        def setup_input_tab(self):
            self.input_frame.columnconfigure(0, weight=1)
            self.input_frame.rowconfigure(2, weight=1)

            input_title = ttk.Label(self.input_frame, text="Nhập thông tin đơn hàng", font=("Arial", 14, "bold"))
            input_title.grid(row=0, column=0, columnspan=4, pady=10, padx=5, sticky="w")

            form_frame = ttk.LabelFrame(self.input_frame, text="Thông tin chi tiết", padding=(10, 5))
            form_frame.grid(row=1, column=0, columnspan=4, padx=5, pady=5, sticky="new")
            form_frame.columnconfigure(0, weight=1, uniform="form_col")
            form_frame.columnconfigure(1, weight=2, uniform="form_col")
            form_frame.columnconfigure(2, weight=1, uniform="form_col")
            form_frame.columnconfigure(3, weight=2, uniform="form_col")

            # Điểm đi
            ttk.Label(form_frame, text="Điểm đi:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
            self.ff_from_location = ttk.Entry(form_frame)
            self.ff_from_location.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

            # Điểm đến
            ttk.Label(form_frame, text="Điểm đến:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
            self.ff_to_location = ttk.Entry(form_frame)
            self.ff_to_location.grid(row=0, column=3, padx=5, pady=5, sticky="ew")

            # Điểm giao
            ttk.Label(form_frame, text="Điểm giao (nếu có):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
            self.ff_delivery_point = ttk.Entry(form_frame)
            self.ff_delivery_point.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

            # Khoảng cách (bắt buộc)
            ttk.Label(form_frame, text="Khoảng cách (km): *").grid(row=1, column=2, padx=5, pady=5, sticky="w")
            self.ff_distance = ttk.Entry(form_frame)
            self.ff_distance.grid(row=1, column=3, padx=5, pady=5, sticky="ew")

            # Trọng lượng thực (bắt buộc)
            ttk.Label(form_frame, text="Trọng lượng thực (kg): *").grid(row=2, column=0, padx=5, pady=5, sticky="w")
            self.ff_actual_weight = ttk.Entry(form_frame)
            self.ff_actual_weight.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

            # Loại hàng
            ttk.Label(form_frame, text="Loại hàng:").grid(row=2, column=2, padx=5, pady=5, sticky="w")
            self.ff_goods_type_var = tk.StringVar(value="Hàng đóng hộp tiêu dùng")
            self.ff_goods_type = ttk.Combobox(form_frame, textvariable=self.ff_goods_type_var,
                                             values=list(self.calculator.config["goods_coefficients"].keys()),
                                             state='readonly')
            self.ff_goods_type.grid(row=2, column=3, padx=5, pady=5, sticky="ew")

            # Kích thước
            ttk.Label(form_frame, text="Kích thước (cm):").grid(row=3, column=0, padx=5, pady=5, sticky="nw")
            dimension_frame = ttk.Frame(form_frame)
            dimension_frame.grid(row=3, column=1, columnspan=3, padx=5, pady=5, sticky="ew")

            ttk.Label(dimension_frame, text="Dài:").pack(side=tk.LEFT, padx=(0,2))
            self.ff_length = ttk.Entry(dimension_frame, width=8)
            self.ff_length.pack(side=tk.LEFT, padx=(0,10))

            ttk.Label(dimension_frame, text="Rộng:").pack(side=tk.LEFT, padx=(0,2))
            self.ff_width = ttk.Entry(dimension_frame, width=8)
            self.ff_width.pack(side=tk.LEFT, padx=(0,10))

            ttk.Label(dimension_frame, text="Cao:").pack(side=tk.LEFT, padx=(0,2))
            self.ff_height = ttk.Entry(dimension_frame, width=8)
            self.ff_height.pack(side=tk.LEFT, padx=(0,10))

            # Số lượng
            ttk.Label(form_frame, text="Số lượng (kiện):").grid(row=4, column=0, padx=5, pady=5, sticky="w")
            self.ff_quantity = ttk.Spinbox(form_frame, from_=1, to=10000, increment=1)
            self.ff_quantity.grid(row=4, column=1, padx=5, pady=5, sticky="ew")
            self.ff_quantity.set(1)

            # Loại xe
            ttk.Label(form_frame, text="Loại xe:").grid(row=4, column=2, padx=5, pady=5, sticky="w")
            self.ff_vehicle_type_var = tk.StringVar(value="Tải")
            self.ff_vehicle_type = ttk.Combobox(form_frame, textvariable=self.ff_vehicle_type_var,
                                               values=list(self.calculator.config["vehicle_coefficients"].keys()),
                                               state='readonly')
            self.ff_vehicle_type.grid(row=4, column=3, padx=5, pady=5, sticky="ew")

            # Hệ số đề xuất
            ttk.Label(form_frame, text="Hệ số đề xuất:").grid(row=5, column=0, padx=5, pady=5, sticky="w")
            self.ff_proposed_coeff = ttk.Entry(form_frame)
            self.ff_proposed_coeff.grid(row=5, column=1, padx=5, pady=5, sticky="ew")
            self.ff_proposed_coeff.insert(0, "1.0")

            # Nút tính toán
            calculate_button = ttk.Button(self.input_frame, text="Tính toán", command=self.calculate_from_form,
                                         style='Accent.TButton')
            calculate_button.grid(row=2, column=0, columnspan=4, padx=5, pady=15)

            # Khu vực kết quả
            result_frame = ttk.LabelFrame(self.input_frame, text="Kết quả tính toán", padding=(10, 5))
            result_frame.grid(row=3, column=0, columnspan=4, padx=5, pady=5, sticky="nsew")
            result_frame.rowconfigure(0, weight=1)
            result_frame.columnconfigure(0, weight=1)

            self.result_display = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD, height=10, font=("Arial", 11),
                                                           state=tk.DISABLED, padx=5, pady=5, relief=tk.SUNKEN, borderwidth=1)
            self.result_display.grid(row=0, column=0, sticky="nsew")
            self.result_display.tag_config("bold_result", font=("Arial", 11, "bold"))

        def setup_help_tab(self):
            self.help_frame.rowconfigure(1, weight=1)
            self.help_frame.columnconfigure(0, weight=1)

            help_title = ttk.Label(self.help_frame, text="Hướng dẫn sử dụng", font=("Arial", 14, "bold"))
            help_title.grid(row=0, column=0, pady=10, padx=5, sticky="w")

            help_content = scrolledtext.ScrolledText(self.help_frame, wrap=tk.WORD, font=("Arial", 11),
                                                    relief=tk.FLAT, padx=5, pady=5)
            help_content.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

            help_text = """
**Hướng dẫn sử dụng Trợ lý báo giá cước vận chuyển**

**Cấu hình:** Các bảng hệ số và hằng số được nhúng trực tiếp trong mã Python.

**1. Tab "Trò chuyện":**
   - Nhập yêu cầu tự nhiên, ví dụ: "Số kilomet: 156, Trọng lượng: 1000 kg" hoặc "Chở 1 tấn từ Nghệ An đến Thanh Hóa, 156km, kích thước 200x300x400, loại xe: Tải, hệ số đề xuất: 1.5".
   - Trợ lý sẽ phân tích và tính cước dựa trên cấu hình nhúng.
   - Tối thiểu cần quãng đường và trọng lượng, các thông tin khác nếu không cung cấp sẽ dùng mặc định (Vùng còn lại, Hàng đóng hộp tiêu dùng, Hệ số = 1).

**2. Tab "Nhập liệu chi tiết":**
   - Điền ít nhất: Khoảng cách (km) và Trọng lượng thực (kg).
   - Các trường khác (Điểm đi, Điểm đến, Điểm giao, Kích thước, Số lượng, Loại hàng, Loại xe, Hệ số đề xuất) là tùy chọn.
   - Nhấn "Tính toán" để xem kết quả chi tiết.
   - Kích thước trống → Không tính trọng lượng quy đổi. Số kiện trống → 1.

**Kết quả:**
   - Hiển thị: Trọng lượng thực, Trọng lượng quy đổi (nếu có), Trọng lượng tính cước, Cước tạm tính, Phí giao tận nơi, Tổng tiền, Giá xe ghép, Giá nguyên xe, Giá báo khách.

**Lưu ý:**
   - Đảm bảo API Key Gemini được cấu hình đúng trong mã.
            """
            help_content.insert(tk.END, help_text)
            help_content.config(state=tk.DISABLED)

        def add_message(self, sender, message, save=True):
            if not message:
                return
            self.chat_display.config(state=tk.NORMAL)
            timestamp = datetime.now().strftime('%d/%m %H:%M:%S')
            prefix = ""
            tag = "assistant"
            if sender == "user":
                prefix = f"Bạn: "
                tag = "user"
            elif sender == "assistant":
                prefix = f"Trợ lý: "
                tag = "assistant"
            elif sender == "error":
                prefix = f"Lỗi: "
                tag = "error"
            self.chat_display.insert(tk.END, f"[{timestamp}] ", "timestamp")
            self.chat_display.insert(tk.END, prefix + message + "\n\n", tag)
            self.chat_display.config(state=tk.DISABLED)
            self.chat_display.see(tk.END)
            if save:
                self.chat_history_list.append({"role": sender, "content": message, "timestamp": timestamp})

        def send_message(self, event=None):
            message = self.chat_input.get().strip()
            if not message:
                return
            self.chat_input.delete(0, tk.END)
            self.add_message("user", message, save=True)
            threading.Thread(target=self.process_message, args=(message,), daemon=True).start()

        def process_message(self, message):
            response = ""
            sender = "assistant"
            try:
                keywords = ['báo giá', 'giá cước', 'vận chuyển', 'chở', 'xe tải', 'hàng hóa', 'gửi hàng', 'chi phí']
                is_quote_request = any(keyword in message.lower() for keyword in keywords)
                parsed_data = self.calculator.parse_user_query(message)
                if not is_quote_request and parsed_data['confidence'] > 0.3:
                    is_quote_request = True

                if is_quote_request:
                    response = self.calculator.process_query(message)
                elif self.model:
                    prompt = f"""Bạn là trợ lý báo giá cước vận chuyển tại Việt Nam, sử dụng logic từ cấu hình nhúng.
Nếu người dùng hỏi về báo giá, tính cước dựa trên thông tin cung cấp. Tối thiểu cần quãng đường và trọng lượng.
Nếu thiếu thông tin, yêu cầu thêm hoặc dùng mặc định. Nếu hỏi khác, trả lời ngắn gọn, lịch sự bằng tiếng Việt.
Câu hỏi: "{message}"
Trả lời:"""
                    ai_response = self.model.generate_content(prompt)
                    response = ai_response.text
                else:
                    response = "Xin lỗi, tôi chỉ hỗ trợ báo giá cước vận chuyển. Vui lòng cung cấp quãng đường và trọng lượng."

            except Exception as e:
                response = f"Lỗi xử lý yêu cầu: {str(e)}"
                sender = "error"
                print(f"Lỗi process_message: {str(e)}")

            self.root.after(0, self.add_message, sender, response, True)

        def calculate_from_form(self):
            result_text = ""
            try:
                distance_km = self.ff_distance.get().strip()
                actual_weight_kg = self.ff_actual_weight.get().strip()
                quantity = self.ff_quantity.get()
                vol_length_cm = self.ff_length.get().strip() or None
                vol_width_cm = self.ff_width.get().strip() or None
                vol_height_cm = self.ff_height.get().strip() or None
                pickup_loc = self.ff_from_location.get().strip() or "Vùng còn lại"
                delivery_loc = self.ff_to_location.get().strip() or "Vùng còn lại"
                delivery_point = self.ff_delivery_point.get().strip()
                goods_type = self.ff_goods_type_var.get()
                vehicle_type = self.ff_vehicle_type_var.get()
                proposed_coeff = self.ff_proposed_coeff.get().strip() or "1.0"

                if not distance_km:
                    raise ValueError("Khoảng cách là bắt buộc.")
                if not actual_weight_kg:
                    raise ValueError("Trọng lượng thực là bắt buộc.")
                if vol_length_cm and (not vol_width_cm or not vol_height_cm):
                    raise ValueError("Cần nhập đủ Dài, Rộng, Cao.")

                dist_val = float(distance_km.replace(',', '.'))
                actual_w_val = float(actual_weight_kg.replace(',', '.'))
                qty_val = int(quantity)
                len_cm = float(vol_length_cm.replace(',', '.')) if vol_length_cm else None
                wid_cm = float(vol_width_cm.replace(',', '.')) if vol_width_cm else None
                hei_cm = float(vol_height_cm.replace(',', '.')) if vol_height_cm else None
                proposed_coeff_val = float(proposed_coeff.replace(',', '.'))

                pickup_zone = self.calculator.get_zone_name_from_loc(pickup_loc)
                delivery_zone = self.calculator.get_zone_name_from_loc(delivery_loc)

                calculation_result = self.calculator.calculate_shipping_rate(
                    distance_km=dist_val,
                    actual_weight_kg=actual_w_val,
                    quantity=qty_val,
                    vol_length_cm=len_cm,
                    vol_width_cm=wid_cm,
                    vol_height_cm=hei_cm,
                    pickup_zone_name=pickup_zone,
                    delivery_zone_name=delivery_zone,
                    delivery_point=delivery_point,
                    goods_type=goods_type,
                    vehicle_type=vehicle_type,
                    proposed_coefficient=proposed_coeff_val
                )

                if calculation_result.get("error"):
                    raise Exception(calculation_result["error"])

                result_text = f"**Kết quả từ {pickup_loc} (Vùng: {pickup_zone}) đến {delivery_loc} (Vùng: {delivery_zone}):**\n\n"
                result_text += f"- Số lượng: {qty_val}\n"
                if len_cm:
                    result_text += f"- Kích thước: {len_cm}x{wid_cm}x{hei_cm} cm\n"
                result_text += f"- Trọng lượng thực: {actual_w_val:.2f} kg\n"
                if calculation_result['volumetric_weight'] > 0:
                    result_text += f"- Trọng lượng quy đổi: {calculation_result['volumetric_weight']:.2f} kg\n"
                result_text += f"- Trọng lượng tính cước: {calculation_result['chargeable_weight']:.2f} kg\n"
                result_text += f"- Khoảng cách: {dist_val} km\n"
                result_text += f"- Loại hàng: {goods_type}\n"
                result_text += f"- Loại xe: {vehicle_type}\n"
                result_text += f"- Hệ số đề xuất: {proposed_coeff_val}\n\n"
                result_text += f"**Giá cước ước tính:**\n"
                result_text += f"- Cước tạm tính: {self.calculator.format_price(calculation_result['base_freight'])} VNĐ\n"
                result_text += f"- Phí giao tận nơi: {self.calculator.format_price(calculation_result['delivery_fee'])} VNĐ\n"
                result_text += f"- Tổng tiền: {self.calculator.format_price(calculation_result['total_cost'])} VNĐ\n"
                result_text += f"- Giá xe ghép: {self.calculator.format_price(calculation_result['shared_vehicle_cost'])} VNĐ\n"
                result_text += f"- Giá nguyên xe: {self.calculator.format_price(calculation_result['full_vehicle_cost'])} VNĐ\n"
                result_text += f"- Giá báo khách: {self.calculator.format_price(calculation_result['customer_price'])} VNĐ\n"

            except ValueError as ve:
                result_text = f"Lỗi nhập liệu: {ve}"
                messagebox.showerror("Lỗi nhập liệu", result_text)
            except Exception as e:
                result_text = f"Lỗi tính toán: {str(e)}"
                messagebox.showerror("Lỗi tính toán", result_text)
                print(f"Lỗi calculate_from_form: {str(e)}")

            self.result_display.config(state=tk.NORMAL)
            self.result_display.delete(1.0, tk.END)
            parts = result_text.split('**')
            for i, part in enumerate(parts):
                if i % 2 == 1:
                    self.result_display.insert(tk.END, part, "bold_result")
                else:
                    self.result_display.insert(tk.END, part)
            self.result_display.config(state=tk.DISABLED)

        def save_chat_history(self):
            if not self.chat_history_list:
                return
            try:
                with open(self.chat_history_file, 'w', encoding='utf-8') as f:
                    json.dump(self.chat_history_list, f, ensure_ascii=False, indent=2)
                print(f"Lịch sử trò chuyện đã lưu vào {self.chat_history_file}")
            except Exception as e:
                print(f"Lỗi khi lưu lịch sử trò chuyện: {str(e)}")

        def load_chat_history(self):
            import os
            if os.path.exists(self.chat_history_file):
                try:
                    with open(self.chat_history_file, 'r', encoding='utf-8') as f:
                        self.chat_history_list = json.load(f)
                    self.chat_display.config(state=tk.NORMAL)
                    self.chat_display.delete(1.0, tk.END)
                    for msg_data in self.chat_history_list:
                        sender = msg_data.get("role", "assistant")
                        message = msg_data.get("content", "")
                        timestamp_str = msg_data.get("timestamp", datetime.now().strftime('%d/%m %H:%M:%S'))
                        prefix = ""
                        tag = "assistant"
                        if sender == "user":
                            prefix = f"Bạn: "
                            tag = "user"
                        elif sender == "assistant":
                            prefix = f"Trợ lý: "
                            tag = "assistant"
                        elif sender == "error":
                            prefix = f"Lỗi: "
                            tag = "error"
                        self.chat_display.insert(tk.END, f"[{timestamp_str}] ", "timestamp")
                        self.chat_display.insert(tk.END, prefix + message + "\n\n", tag)
                    self.chat_display.config(state=tk.DISABLED)
                    self.chat_display.see(tk.END)
                except Exception as e:
                    print(f"Lỗi khi tải lịch sử trò chuyện: {str(e)}")
                    self.chat_history_list = []

if __name__ == "__main__":
    if TKINTER_AVAILABLE:
        root = tk.Tk()
        app = ShippingAssistantApp(root)
        root.mainloop()
    else:
        print("Thư viện Tkinter không khả dụng. Chạy ở chế độ dòng lệnh.")
        calculator = ShippingCalculator()
        print("\n--- Trợ lý báo giá cước (Dòng lệnh) ---")
        while True:
            query = input("Nhập yêu cầu (hoặc 'quit'):> ")
            if query.lower() == 'quit':
                break
            if query:
                response = calculator.process_query(query)
                print("\n--- Kết quả ---")
                print(response)
                print("---------------\n")