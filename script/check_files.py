import fitz
import sys

files_to_check = [13, 14, 17, 18, 19, 20, 21, 22]

for num in files_to_check:
    try:
        pdf = fitz.open(f'input/_raw/{num}.pdf')
        page = pdf[0]
        text_dict = page.get_text('dict')
        
        text_by_size = []
        for block in text_dict['blocks']:
            if block['type'] == 0:
                for line in block['lines']:
                    for span in line['spans']:
                        text = span['text'].strip()
                        if text:
                            text_by_size.append((span['size'], text.upper()))
        
        text_by_size.sort(reverse=True, key=lambda x: x[0])
        
        print(f'\n=== {num}.pdf ===')
        for size, text in text_by_size[:10]:
            print(f'{size:.1f}: {text[:50]}')
        
        pdf.close()
    except Exception as e:
        print(f'\nError with {num}.pdf: {e}')
