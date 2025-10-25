import json
import numpy as np

def check_height_consistency(line):
    heights = [word['height'] for word in line]
    if len(heights) < 2: return 0
    if np.std(heights) >= 0.5: return 30
    return 0

def check_alignment_consistency(line):
    tops = [word['top'] for word in line]
    if len(tops) < 2: return 0
    if np.std(tops) > 1.0: return 30
    return 0

def check_spacing_consistency(line):
    if len(line) < 2: return 0
    line.sort(key=lambda w: w['left'])
    spaces = []
    for i in range(len(line) - 1):
        space = line[i+1]['left'] - (line[i]['left'] + line[i]['width'])
        if space > 0: spaces.append(space)
    if len(spaces) < 1: return 0
    avg_space = np.mean(spaces)
    if avg_space > 0 and np.std(spaces) / avg_space > 0.5: return 20
    return 0

def check_line_spacing_consistency(lines):
    if len(lines) < 3:
        return 0

    # 각 라인의 평균적인 수직 위치 계산
    line_y_positions = []
    for line in lines:
        avg_top = np.mean([word['top'] for word in line])
        line_y_positions.append(avg_top)
    
    # 연속된 라인들 사이의 수직 간격 계산
    line_spaces = []
    for i in range(len(line_y_positions) - 1):
        space = line_y_positions[i+1] - line_y_positions[i]
        if space > 0:
            line_spaces.append(space)
            
    if not line_spaces:
        return 0
    
    avg_space = np.mean(line_spaces)
    if avg_space > 0 and np.std(line_spaces) / avg_space > 0.2:
        return 40 
        
    return 0

def analyze_document_font(json_file_path):
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            ocr_result = json.load(f)
    except FileNotFoundError:
        return {"error": f"파일을 찾을 수 없습니다: {json_file_path}"}

    fields = ocr_result.get("images", [{}])[0].get("fields", [])
    if not fields:
        return {"error": "분석할 텍스트(fields)가 없습니다."}

    processed_words = []
    for field in fields:
        vertices = field.get("boundingPoly", {}).get("vertices", [])
        if len(vertices) == 4 and field.get('inferText'): # 텍스트가 있는 경우만 처리
            processed_words.append({
                'text': field.get("inferText", ""),
                'top': (vertices[0]['y'] + vertices[1]['y']) / 2,
                'height': ((vertices[2]['y'] + vertices[3]['y']) / 2) - ((vertices[0]['y'] + vertices[1]['y']) / 2),
                'left': vertices[0]['x'],
                'width': vertices[1]['x'] - vertices[0]['x']
            })
    
    processed_words.sort(key=lambda w: w['top'])

    lines = []
    if processed_words:
        current_line = [processed_words[0]]
        for word in processed_words[1:]:
            base_word = current_line[0]
            # 같은 라인 판단 기준: 기준 단어 높이의 50% 이내에 있으면 같은 라인으로 간주
            if abs(word['top'] - base_word['top']) < base_word['height'] * 0.5:
                current_line.append(word)
            else:
                lines.append(current_line)
                current_line = [word]
        lines.append(current_line)

    total_score = 0
    
    total_score += check_line_spacing_consistency(lines)
    
    # 각 라인 내부 일관성 검사
    for line in lines:
        total_score += check_height_consistency(line)
        total_score += check_alignment_consistency(line)
        total_score += check_spacing_consistency(line)
    
    # 최종 판정
    decision = "Safe"
    if total_score > 50:
        decision = "Danger"
    elif total_score > 20:
        decision = "Warning"

    return {
        "score": total_score,
        "decision": decision
    }

if __name__ == "__main__":
    result_file = "ocr_result.json" 
    analysis_result = analyze_document_font(result_file)
    print("--- 최종 모듈 테스트 결과 ---")
    print(analysis_result)