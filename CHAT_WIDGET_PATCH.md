# Chat Widget Patch Instructions

Place `core/chat_widget.py` in your `core/` folder (already done ✓).

Then add **2 lines** to each page file:

---

## pages/chat.py

```python
# 1. Add with your existing imports at the top:
from core.chat_widget import render_chat_widget

# 2. Add as the very last line of render():
render_chat_widget(page_key="chat")
```

> **Note:** If `chat.py` already has its own `st.chat_input()`, remove it first —
> Streamlit only allows one `st.chat_input()` per page.

---

## pages/compliance.py

```python
# 1. Add with your existing imports at the top:
from core.chat_widget import render_chat_widget

# 2. Add as the very last line of render():
render_chat_widget(page_key="compliance")
```

---

## pages/dashboard.py

```python
# 1. Add with your existing imports at the top:
from core.chat_widget import render_chat_widget

# 2. Add as the very last line of render():
render_chat_widget(page_key="dashboard")
```

---

## pages/ehr_summarizer.py

```python
# 1. Add with your existing imports at the top:
from core.chat_widget import render_chat_widget

# 2. Add as the very last line of render():
render_chat_widget(page_key="ehr_summarizer")
```

---

## pages/news.py

```python
# 1. Add with your existing imports at the top:
from core.chat_widget import render_chat_widget

# 2. Add as the very last line of render():
render_chat_widget(page_key="news")
```

---

## Final project structure

```
health-self-healing-hermes/
├── app.py
├── CHAT_WIDGET_PATCH.md        ← this file
├── core/
│   ├── chat_widget.py          ← new ✓
│   ├── config.py
│   ├── db.py
│   ├── gemini.py
│   └── session.py
└── pages/
    ├── chat.py                 ← add 2 lines
    ├── compliance.py           ← add 2 lines
    ├── dashboard.py            ← add 2 lines
    ├── ehr_summarizer.py       ← add 2 lines
    ├── imaging.py              ← already done ✓
    └── news.py                 ← add 2 lines
```
