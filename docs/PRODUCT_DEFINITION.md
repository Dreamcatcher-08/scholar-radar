# Scholar Radar · 产品定义与边界

> v3 · 2026-05-08 已实施。学者追踪引擎，只做一件事。

---

## 一句话定义

**Scholar Radar 是一个学者追踪系统。** 只回答一个问题：**"我关注的学者最近发表了什么？"**

当前追踪：**江小涓、李国杰**（后续可扩充，但保持学者维度一致）

---

## 产品边界

| 维度 | ✅ Scholar Radar 做 | ❌ Scholar Radar 不做 |
|------|---------------------|------------------------|
| **追踪对象** | 特定学者的学术产出 | 机构/智库/主题/领域 |
| **信息类型** | 学术论文、预印本 | 政策报告、新闻、RSS |
| **信源** | arXiv、Semantic Scholar、OpenAlex | 智库官网、政府网站、新闻媒体 |
| **受众** | 张老师本人 | 不做大众展示 |
| **输出** | 结构化动态列表（单页 HTML） | 不产出政策分析、不产出文献综述 |

---

## 数据模型

```json
{
  "scholars": [
    {"name": "江小涓", "keywords": ["Jiang Xiaojuan", "江小涓", "Xiaojuan Jiang"]},
    {"name": "李国杰", "keywords": ["Li Guojie", "李国杰", "Guojie Li"]}
  ],
  "items": [
    {
      "id": "arxiv:2505.12345",
      "source": "arXiv",
      "source_type": "preprint",
      "title": "...",
      "authors": [...],
      "url": "https://arxiv.org/abs/2505.12345",
      "published_date": "2026-05-07",
      "matched_scholar": "江小涓"
    }
  ]
}
```

`source_type` 只用学术分类：`preprint` / `paper`。

---

## 2026-05-08 清理记录

| # | 清理项 | 动作 |
|---|--------|------|
| 1 | `TRACKED_TOPICS`（主题搜索） | 删除 |
| 2 | `collect_policy_rss()`（智库RSS） | 整个函数删除 |
| 3 | `TRACKED_PEOPLE` 外籍学者 | 移除 Acemoglu、Amodei |
| 4 | 信源只保留三个 | arXiv + Semantic Scholar + OpenAlex |
| 5 | HTML 过滤按钮 | 从 subject/topic/type 简化为 scholar |
| 6 | 字段标准化 | `matched_query` → `matched_scholar`，去掉 matched_subject/matched_topic |

---

## 一句话总结

**干净。只做人，不做别的。** 张老师看到页面就知道：今天江小涓和李国杰发了什么。
