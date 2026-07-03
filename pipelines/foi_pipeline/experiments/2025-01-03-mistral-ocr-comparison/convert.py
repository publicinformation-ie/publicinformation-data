#!/usr/bin/env python3
"""Convert Mistral OCR markdown tables to pipeline rows format."""
import re


def parse_markdown_table(table_text):
    """Parse a single markdown table into rows.
    
    Handles multi-line cells where content continues on the next line
    without the leading | character.
    
    Args:
        table_text: String containing a markdown table
        
    Returns:
        List of lists representing the table rows
    """
    lines = table_text.strip().split('\n')
    if not lines:
        return []
    
    rows = []
    current_row = []
    in_table = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Skip separator lines (|---|---|) - lines that contain only |, -, :, and spaces
        # Match lines like |---|---| or |:--:|:--:| etc.
        if re.match(r'^\|[\s\-:|]+\|$', line):
            in_table = True
            continue
        
        # Check if this line starts a new table row (starts with |)
        if line.startswith('|'):
            # If we have a current row, save it
            if current_row:
                rows.append(current_row)
                current_row = []
            in_table = True
            # Parse table row - remove leading/trailing | and split
            line = line.strip()
            if line.startswith('|'):
                line = line[1:]
            if line.endswith('|'):
                line = line[:-1]
            cells = [cell.strip() for cell in line.split('|') if cell.strip()]
            current_row = cells
        elif in_table and current_row:
            # This line doesn't start with |, so it's a continuation of the previous row
            # Strip any trailing | from the line and append to the last cell
            continuation = line.rstrip('|').strip()
            if continuation:
                current_row[-1] = current_row[-1] + '\n' + continuation
        elif in_table:
            # Empty line or line without | but in table context
            # Treat as continuation or skip
            pass
    
    # Don't forget the last row
    if current_row:
        rows.append(current_row)
    
    return rows


def strip_markdown_formatting(text):
    """Strip markdown formatting from text.
    
    Removes bold, italic, code, and other common markdown formatting.
    """
    if not text:
        return text
    
    # Remove **bold**
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    # Remove *italic*
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # Remove `code`
    text = re.sub(r'`(.+?)`', r'\1', text)
    # Remove ~~strikethrough~~
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    # Remove links [text](url)
    text = re.sub(r'\[(.+?)\]\([^)]*\)', r'\1', text)
    
    return text


def markdown_to_rows(markdown):
    """Convert Mistral OCR markdown output to pipeline rows format.
    
    Handles:
    - Multiple tables separated by --- (page breaks)
    - Multi-line cells (joined with space)
    - Markdown formatting (stripped from cells)
    
    Args:
        markdown: Raw markdown output from Mistral OCR
        
    Returns:
        List of rows, where each row is a list of cell values.
        Returns [] if no tables found.
    """
    if not markdown or not markdown.strip():
        return []
    
    all_rows = []
    
    # Split by page break separator
    sections = re.split(r'\n---\n', markdown)
    
    for section in sections:
        if not section.strip():
            continue
        
        # Normalize line endings and handle multi-line cells
        # First, handle cells that span multiple lines
        section = section.replace('\r\n', '\n')
        
        # Parse the table
        table_rows = parse_markdown_table(section)
        
        if table_rows:
            # Process multi-line cells: if a cell contains newlines, 
            # it means the markdown table had line breaks within a cell
            # We join these with spaces
            processed_rows = []
            for row in table_rows:
                processed_row = []
                for cell in row:
                    # Join multi-line content with space
                    cell = cell.replace('\n', ' ')
                    # Strip markdown formatting
                    cell = strip_markdown_formatting(cell)
                    processed_row.append(cell)
                processed_rows.append(processed_row)
            
            all_rows.extend(processed_rows)
    
    return all_rows
