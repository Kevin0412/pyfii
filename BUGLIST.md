# 待修改的BUG列表

- 保存不能指定路径
```python
F=pf.Fii('output/测试',[d1], 'test.mp3')

#[Errno 2] No such file or directory: 'output/测试/output/测试.fii'
```

- 项目没有音乐时不能预览
```python
F=pf.Fii('测试',[d1])#命名,[所有无人机名],music选择性添加
# pf.show(data,t0,music)
# pygame.error: Couldn't read first 12 bytes of audio data
```