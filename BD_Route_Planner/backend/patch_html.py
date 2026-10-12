import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the actions card section
old_block = (
    '    <!-- \u2500\u2500\u2500 Actions \u2500\u2500\u2500 -->\n'
    '    <div class="section-card">\n'
    '      <button class="btn btn-primary" id="run-btn" disabled>\u25b6  Run Algorithm</button>\n'
    '      <button class="btn btn-accent"  id="run-all-btn" disabled>\u26a1  Run All &amp; Compare</button>\n'
    '    </div>'
)

new_block = (
    '    <!-- \u2500\u2500\u2500 Actions \u2500\u2500\u2500 -->\n'
    '    <div class="section-card">\n'
    '      <div class="anim-speed-row">\n'
    '        <label for="anim-speed">\u26a1 Speed</label>\n'
    '        <input type="range" id="anim-speed" min="1" max="5" value="3" step="1" />\n'
    '        <span class="slider-val" id="anim-speed-val">3</span>\n'
    '      </div>\n'
    '      <button class="btn btn-primary" id="run-btn" disabled>\u25b6  Run Algorithm</button>\n'
    '      <button class="btn btn-accent"  id="run-all-btn" disabled>\u26a1  Run All &amp; Compare</button>\n'
    '      <button class="btn btn-ghost btn-sm" id="clear-path-btn" style="margin-top:4px" disabled>\U0001f5d1 Clear Path &amp; Explored</button>\n'
    '    </div>'
)

if old_block in content:
    content = content.replace(old_block, new_block, 1)
    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print('SUCCESS: actions card updated')
else:
    print('NOT FOUND. Searching for partial match...')
    idx = content.find('id="run-btn"')
    print(repr(content[max(0,idx-100):idx+200]))
