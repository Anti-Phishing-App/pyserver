# stamp.py
import cv2
import numpy as np

def run_stamp_detection(image_path: str):
    """
    이미지에서 빨간색 계열 직인 영역을 탐지하고 bounding box 좌표 반환.
    반환 값은 JSON 직렬화 가능한 dict 형태여야 함.
    """

    try:
        # 이미지 로드
        image = cv2.imread(image_path)
        if image is None:
            return {"error": True, "message": "이미지를 불러올 수 없습니다."}

        # 색상공간 변환 (BGR → HSV)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # 빨간색 범위 마스크
        lower_red1 = np.array([0, 40, 50])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([170, 40, 50])
        upper_red2 = np.array([180, 255, 255])

        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask = cv2.bitwise_or(mask1, mask2)

        # 모폴로지 연산으로 노이즈 제거
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # 컨투어 탐색
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        boxes = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 1000:  # 너무 작은 건 노이즈로 제외
                x, y, w, h = cv2.boundingRect(cnt)
                boxes.append({"x": int(x), "y": int(y), "width": int(w), "height": int(h)})

        # 탐지된 박스 수에 따른 점수 계산 (임시 로직)
        score = min(len(boxes) * 0.3, 1.0)

        return {
            "error": False,
            "count": len(boxes),
            "boxes": boxes,
            "score": round(score, 2)
        }

    except Exception as e:
        return {"error": True, "message": str(e)}
