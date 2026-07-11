# after-reading

一个把原始阅读记录、人工策展、短判断与时间轨迹串起来的公开阅读系统。

[在线书架](https://estelledc.github.io/after-reading/) · [Jason Hub](https://estelledc.github.io/) · [About](https://estelledc.github.io/about/) · [Resume](https://estelledc.github.io/resume/)

## 它解决什么

普通书单通常只保留书名、数量和日期。after-reading 试着回答更难的问题：为什么这本书值得进入公开书架，它和当时的生活有什么关系，读完后留下了什么判断。

公开页面保留书架原有的杂食气质：严肃文学、网文、推理、杂志和工具书并列，不用题材制造“阅读等级”。

## 可核验的当前证据

- 73 个唯一策展 ID，全部能在原始缓存中找到，且源字段 `finishReading=1`。
- 8 个由人工维护的分类。
- 73/73 个策展条目具备对应的一句话判断。
- 4 个按书组织的笔记目录，以及 1 组早期划线实验；深浅不同，因此不统一称作“深度笔记”。

这些数字描述的是当前仓库状态，不代表阅读效果、知识留存或笔记质量。

## 生成链路

```text
data/raw-shelf.json
        ↓
content/curation.yaml + content/jason-takes.md + content/identity.md
        ↓
scripts/build_shelf.py
        ↓
index.html
        ↓
scripts/validate_shelf.py
```

- `raw-shelf.json` 保存同步缓存，不直接等于公开书架。
- `curation.yaml` 决定公开范围与分类。
- `jason-takes.md` 保存短判断，`identity.md` 保存页面叙事。
- 生成器输出无框架的静态页面；验证器检查数据匹配、完读标记、唯一性、点评覆盖、页面结构、可访问入口与分享 metadata。

## Jason 与 AI 的边界

Jason 决定公开书目、分类、哪些判断可以代表自己，并负责最终公开验收。AI 可以辅助整理数据、生成页面、检查一致性和打磨表达，但不能替代完读事实，也不能把某条点评自行标记为“已人工复核”。

当前数据结构没有逐条记录点评的人审状态，这是已知限制。

## 本地生成与验证

需要 Python 3 和 PyYAML：

```bash
python -m pip install pyyaml
python scripts/build_shelf.py
python scripts/build_shelf.py --check
python scripts/validate_shelf.py
python -m unittest discover -s tests -v
```

## Limitations

The finished state comes from a cached external-platform field, not independent verification. Short takes are memory anchors rather than formal reviews, and per-entry human-review status is not yet tracked.
