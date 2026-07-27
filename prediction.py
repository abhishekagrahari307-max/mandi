from datetime import datetime


def predict_future_prices(historical_data, crop_name):
    """Return a deterministic linear trend from verified historical points.

    This is a statistical projection, not an AI trading recommendation. It
    refuses to return a value when fewer than three observations are present.
    """
    crop_history = historical_data.get(crop_name, [])
    valid_points = [
        point for point in crop_history
        if isinstance(point, dict) and isinstance(point.get("price"), (int, float))
    ]
    if len(valid_points) < 3:
        raise ValueError("At least three verified historical observations are required")

    prices = [float(point["price"]) for point in valid_points]
    n = len(prices)
    x_values = list(range(n))
    sum_x = sum(x_values)
    sum_y = sum(prices)
    sum_xx = sum(value * value for value in x_values)
    sum_xy = sum(x_values[index] * prices[index] for index in range(n))
    denominator = n * sum_xx - sum_x * sum_x
    slope = (n * sum_xy - sum_x * sum_y) / denominator if denominator else 0.0
    intercept = (sum_y - slope * sum_x) / n

    fitted = [intercept + slope * value for value in x_values]
    mean_price = sum_y / n
    total_variance = sum((price - mean_price) ** 2 for price in prices)
    residual_variance = sum((prices[index] - fitted[index]) ** 2 for index in range(n))
    r_squared = 1.0 - residual_variance / total_variance if total_variance else 1.0
    model_fit = max(0, min(100, round(r_squared * 100)))

    if slope > 8:
        trend_direction = "Upward (तेजी)"
    elif slope < -8:
        trend_direction = "Downward (मंदी)"
    else:
        trend_direction = "Stable (स्थिर)"

    base_price = prices[-1]
    projections = {
        "tomorrow": max(0, round(base_price + slope)),
        "three_days": max(0, round(base_price + slope * 3)),
        "seven_days": max(0, round(base_price + slope * 7)),
    }
    return {
        "crop": crop_name,
        "current_price": round(base_price),
        "trend": trend_direction,
        "slope": round(slope, 2),
        "confidence": f"{model_fit}% model fit",
        "observation_count": n,
        "predictions": projections,
        "recommendation_hi": "यह केवल सत्यापित ऐतिहासिक भावों की रैखिक प्रवृत्ति है; खरीद-बिक्री की सलाह नहीं।",
        "recommendation_en": "This is only a linear trend of verified historical prices, not trading advice.",
        "generated_at": datetime.now().isoformat(),
    }
