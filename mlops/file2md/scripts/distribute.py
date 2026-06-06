import re

def _get_chapter_page_ranges(text_parts, boundaries):
    """通过章节边界的行号估算各章的页码范围。
    
    假设每页约30行文本。
    Returns: dict {chapter_num: (start_page, end_page)}
    """
    if not boundaries:
        return {}
    
    # 估算总页数：从边界文本行索引推算
    total_lines = len(text_parts)
    est_pages = max(1, total_lines // 30)
    
    ch_ranges = {}
    for i, (ch, title, line_idx) in enumerate(boundaries):
        next_line_idx = boundaries[i+1][2] if i+1 < len(boundaries) else total_lines
        start_page = max(1, line_idx // 30 + 1)
        end_page = max(start_page, next_line_idx // 30 + 1)
        ch_ranges[ch] = (start_page, end_page)
    
    return ch_ranges


def distribute_items_to_chapters(ch_data, text_parts, boundaries, images, tables):
    """将图片和表格按页码分配到对应章节。"""
    ch_page_ranges = _get_chapter_page_ranges(text_parts, boundaries)
    
    if not ch_page_ranges:
        # 无法估算页范围，按章节数均分
        total = len(boundaries)
        for i, (ch, title, _) in enumerate(boundaries):
            start = i * len(images) // total
            end = (i+1) * len(images) // total
            ch_data[ch]['images'] = images[start:end]
            start_t = i * len(tables) // total
            end_t = (i+1) * len(tables) // total
            ch_data[ch]['tables'] = tables[start_t:end_t]
        return
    
    # 按页范围分配图片
    for img in images:
        img_page = img.get('page', 1)
        for ch, (sp, ep) in ch_page_ranges.items():
            if sp <= img_page <= ep:
                ch_data[ch]['images'].append(img)
                break
        else:
            # 超出范围，归到最后一章
            ch_data[boundaries[-1][0]]['images'].append(img)
    
    # 按页范围分配表格
    for tbl in tables:
        tbl_page = tbl.get('page', 1)
        for ch, (sp, ep) in ch_page_ranges.items():
            if sp <= tbl_page <= ep:
                ch_data[ch]['tables'].append(tbl)
                break
        else:
            ch_data[boundaries[-1][0]]['tables'].append(tbl)
