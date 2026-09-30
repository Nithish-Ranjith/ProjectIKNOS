import os
import re

replacements = {
    '--accent-dark': '--color-terracotta',
    '--muted-dark': '--color-text-secondary',
    '--line-dark': '--color-border',
    '--bg-panel': '--color-bg-raised',
    '--font-header': '--font-ui',
    
    '--accent': '--color-navy',
    '--accent-bg': 'transparent',
    '--accent-border': '--color-navy',
    '--accent-dim': 'transparent',
    '--amber': '--color-warning',
    '--amber-dim': 'transparent',
    '--bg': '--color-bg',
    '--border': '--color-border',
    '--border-mid': '--color-border-mid',
    '--font-body': '--font-ui',
    '--font-system': '--font-ui',
    '--green': '--color-sage',
    '--green-dim': 'transparent',
    '--ink-100': '--color-border',
    '--ink-200': '--color-text-secondary',
    '--ink-600': '--color-text-primary',
    '--panel': '--color-bg-raised',
    '--shadow': '--shadow-panel',
    '--social-bg': 'transparent',
    '--steel-blue': '--color-navy',
    '--text-1': '--color-text-primary',
    '--text-2': '--color-text-secondary',
    '--text-3': '--color-text-secondary',
    '--text-4': '--color-border-mid',
    '--text-h': '--color-text-primary',
}

def replace_in_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    new_content = content
    for old, new in replacements.items():
        new_content = re.sub(rf'var\({old}\)', f'var({new})', new_content)
        
    if new_content != content:
        with open(filepath, 'w') as f:
            f.write(new_content)
        print(f"Updated {filepath}")

for root, dirs, files in os.walk('/Users/nithishranjith/AndroidStudioProjects/ProjectIKNOS/webapp/src'):
    for file in files:
        if file.endswith(('.tsx', '.ts', '.css')):
            replace_in_file(os.path.join(root, file))
