from flask import Flask, request, jsonify
from calculator import ShippingCalculator

app = Flask(__name__)
calc = ShippingCalculator()

@app.route("/baogia", methods=["POST"])
def baogia():
    data = request.get_json()

    loaihang = data.get("loaihang", "Hàng tiêu dùng")
    diemnhan = data.get("diemnhan", "")
    diemgiao = data.get("diemgiao", "")
    km = float(data.get("km", 0))
    sokien = int(data.get("sokien", 1))
    trongluong = float(data.get("trongluong", 0))

    giacuoc = calc.calculate_cost(
        km=km,
        weight=trongluong,
        goods_type=loaihang,
        zone="Vùng còn lại"
    )

    return jsonify({
        "loaihang": loaihang,
        "diemnhan": diemnhan,
        "diemgiao": diemgiao,
        "km": km,
        "sokien": sokien,
        "trongluong": trongluong,
        "gia": giacuoc
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
