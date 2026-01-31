import re
from pathlib import Path


def number_to_chinese(num_str):
    """将阿拉伯数字转换为汉字数字读法"""
    # 数字映射
    num_map = {
        '0': '零', '1': '一', '2': '二', '3': '三', '4': '四',
        '5': '五', '6': '六', '7': '七', '8': '八', '9': '九'
    }
    
    # 单位映射
    unit_map = ['', '十', '百', '千', '万']
    
    def convert_number(n):
        """转换数字为汉字（支持完整读法，如25 -> 二十五，年份逐位转换如2026 -> 二零二六）"""
        n_int = int(float(n))
        n_str = str(n_int)
        
        # 年份特殊处理：4位数且 >= 1000 的年份使用逐位转换（如2026 -> 二零二六）
        if 1000 <= n_int < 10000 and len(n_str) == 4:
            return ''.join([num_map.get(d, d) for d in n_str])
        
        # 对于较小的数字（<10000），使用完整读法
        if n_int < 10000:
            if n_int == 0:
                return '零'
            if n_int < 10:
                return num_map[str(n_int)]
            if n_int < 20:
                if n_int == 10:
                    return '十'
                return '十' + num_map[str(n_int % 10)]
            if n_int < 100:
                tens = n_int // 10
                ones = n_int % 10
                result = num_map[str(tens)] + '十'
                if ones > 0:
                    result += num_map[str(ones)]
                return result
            if n_int < 1000:
                hundreds = n_int // 100
                remainder = n_int % 100
                result = num_map[str(hundreds)] + '百'
                if remainder > 0:
                    if remainder < 10:
                        result += '零' + num_map[str(remainder)]
                    else:
                        result += convert_number(remainder)
                return result
            if n_int < 10000:
                thousands = n_int // 1000
                remainder = n_int % 1000
                result = num_map[str(thousands)] + '千'
                if remainder > 0:
                    if remainder < 100:
                        result += '零' + convert_number(remainder)
                    else:
                        result += convert_number(remainder)
                return result
        else:
            # 对于大数字，逐位转换
            return ''.join([num_map.get(d, d) for d in n_str])
    
    def replace_number(match):
        """替换数字为汉字"""
        num_str = match.group(0)
        # 如果是小数
        if '.' in num_str:
            parts = num_str.split('.')
            int_part = convert_number(parts[0])
            dec_part = ''.join([num_map.get(d, d) for d in parts[1]])
            return int_part + '点' + dec_part
        else:
            return convert_number(num_str)
    
    # 先处理带单位的数字（如"25万"、"100万"）
    # 匹配模式：数字 + 单位（万、千、百等）
    def replace_with_unit(match):
        num_part = match.group(1)
        unit = match.group(2)
        converted_num = convert_number(num_part)
        return converted_num + unit
    
    # 先替换带单位的数字
    result = re.sub(r'(\d+\.?\d*)([万千百十])', replace_with_unit, num_str)
    # 再替换剩余的数字
    result = re.sub(r'\d+\.?\d*', replace_number, result)
    
    return result


def clean_text(text):
    """清洗文本：
    1. 阿拉伯数字转汉字
    2. 逗号改句号
    3. 每句一行
    4. 去掉所有空格
    """
    # 1. 替换非标准标签
    text = text.replace('[uv_break]', '[break_6]').replace('[laugh]', '[laugh_0]')
    
    # 2. 阿拉伯数字转汉字
    text = number_to_chinese(text)
    
    # 3. 逗号改句号
    text = text.replace('，', '。').replace(',', '。')
    
    # 4. 按句号分割，每句一行
    sentences = text.split('。')
    sentences = [s.strip() for s in sentences if s.strip()]
    
    # 5. 去掉每句中的空格
    cleaned_sentences = [s.replace(' ', '') for s in sentences]
    
    # 重新组合，每句一行，最后加句号
    result = '\n'.join([s + '。' for s in cleaned_sentences if s])
    
    return result


def split_by_paragraph(text):
    """按段落拆分文本"""
    # 按双换行符或更多换行符分割段落
    paragraphs = re.split(r'\n\s*\n+', text.strip())
    # 过滤空段落
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    return paragraphs


def merge_paragraphs(paragraphs, min_chars=50, max_chars=200):
    """智能合并段落 - 贪婪模式
    参数：
        paragraphs: 段落列表
        min_chars: 最小字数
        max_chars: 最大字数
    返回：
        合并后的段落列表
    """
    if not paragraphs:
        return []
    
    # 辅助函数：拆分超长文本
    def split_recursive(text, limit):
        if len(text) <= limit:
            return [text]
        
        # 寻找最佳切割点（句号、问号、叹号等）
        split_point = -1
        # 优先在后半部分找句末标点
        for char in ['。', '！', '？', '……', '；', '，']:
            pos = text.rfind(char, 0, limit)
            if pos > limit * 0.5: # 至少保留一半
                split_point = pos + 1
                break
        
        if split_point == -1:
            # 没找到标点，硬切
            split_point = limit
            
        return [text[:split_point]] + split_recursive(text[split_point:], limit)

    merged = []
    current_buffer = ""
    
    for para in paragraphs:
        # 清理多余空行，保持紧凑
        para = para.strip()
        if not para:
            continue
            
        # 预测合并后的长度
        # 加上换行符作为连接
        if current_buffer:
            predicted_len = len(current_buffer) + 1 + len(para)
        else:
            predicted_len = len(para)
            
        # 决策逻辑：
        # 1. 如果加上当前段落不超过 max_chars，直接合并
        if predicted_len <= max_chars:
            if current_buffer:
                current_buffer += "\n" + para
            else:
                current_buffer = para
        else:
            # 2. 如果加上会超过，说明当前 buffer 此刻是满的（或者虽然不满但加不进去了）
            #    先把 current_buffer 处理掉
            if current_buffer:
                # 检查 buffer 是否过长（虽然逻辑上控制了，但防万一）
                if len(current_buffer) > max_chars:
                    merged.extend(split_recursive(current_buffer, max_chars))
                else:
                    merged.append(current_buffer)
                
                # 重置 buffer
                current_buffer = ""
            
            # 3. 处理当前的这个 para（因为它没挤进去）
            #    如果 para 本身就很长，直接切分
            if len(para) > max_chars:
                splits = split_recursive(para, max_chars)
                # 最后一个片段可能很短，留给 buffer
                merged.extend(splits[:-1])
                current_buffer = splits[-1]
            else:
                current_buffer = para
                
    # 处理最后的缓冲区
    if current_buffer:
         if len(current_buffer) > max_chars:
             merged.extend(split_recursive(current_buffer, max_chars))
         else:
             # 尝试合并到上一个（如果太短）
             if len(current_buffer) < min_chars and merged:
                 last = merged[-1]
                 if len(last) + 1 + len(current_buffer) <= max_chars:
                     merged[-1] = last + "\n" + current_buffer
                 else:
                     merged.append(current_buffer)
             else:
                 merged.append(current_buffer)
                 
    return merged


def filter_markdown_metadata(content):
    """过滤掉Markdown文件的元数据（标题、TTS设置建议等）
    
    移除：
    - 以 # 开头的标题行
    - 包含 **[TTS Setting Suggestion]** 的段落
    - 以 * ** 开头的列表项（TTS设置建议）
    """
    lines = content.split('\n')
    filtered_lines = []
    skip_next = False
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # 跳过以 # 开头的标题行
        if stripped.startswith('#'):
            continue
        
        # 跳过包含 TTS Setting Suggestion 的行
        if 'TTS Setting Suggestion' in stripped or 'TTSSettingSuggestion' in stripped:
            skip_next = True
            continue
        
        # 跳过 TTS 设置建议的列表项（以 * ** 开头）
        if stripped.startswith('* **') and ('Role' in stripped or 'Speed' in stripped or 'Note' in stripped):
            continue
        
        # 如果上一行是TTS设置建议标题，跳过后续的空行和列表项
        if skip_next:
            if not stripped or stripped.startswith('*'):
                continue
            else:
                skip_next = False
        
        filtered_lines.append(line)
    
    return '\n'.join(filtered_lines)


def process_markdown_file(file_path, min_chars=50, max_chars=200):
    """处理markdown文件：读取、清洗、按段落拆分、智能合并
    
    参数：
        file_path: 文件路径
        min_chars: 最小字数（默认50），低于此值会合并多个段落
        max_chars: 最大字数（默认200），超过此值会拆分段落
    返回：
        处理后的段落列表
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 先过滤掉Markdown元数据
    content = filter_markdown_metadata(content)
    
    # 再按段落拆分
    paragraphs = split_by_paragraph(content)
    
    # 清洗每个段落
    cleaned_paragraphs = [clean_text(p) for p in paragraphs]
    
    # 智能合并段落
    merged_paragraphs = merge_paragraphs(cleaned_paragraphs, min_chars, max_chars)
    
    return merged_paragraphs


if __name__ == "__main__":
    # 测试
    test_text = "今天是2026年1月28日。兄弟们，AI圈这24小时发生的事，基本上宣告了只会聊天的大模型时代正式结束了。"
    print("原始文本:")
    print(test_text)
    print("\n清洗后:")
    print(clean_text(test_text))
    
    print("\n段落拆分测试:")
    test_paragraphs = "段落1\n\n段落2\n\n段落3"
    print(split_by_paragraph(test_paragraphs))
