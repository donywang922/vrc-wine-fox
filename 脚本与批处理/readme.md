##### 批处理脚本与处理后的模型



脚本完全由Gemini生成，未做任何修改。



##### 结构

items/ -- 原始物品贴图文件

objs/ -- 有独立模型的物品经由blockbench导出的obj文件

output\_item\_models/ -- 由gen\_item\_models.py从items文件夹生成的物品模型obj文件

outputs/ -- 由merge\_objs.py对objs文件夹和output\_item\_models文件夹中所有模型重排uv后的obj文件。

m1-4.png -- 生成物品模型时的遮罩，每个物品按照黑色部分拆分为四个网格体。

gen\_item\_models.py -- 为items文件夹中的图片生成物品模型，用m1-4作为遮罩拆分网格体。输出到output\_item\_models文件夹。

merge\_objs.py -- 合并objs文件夹和output\_item\_models文件夹中模型的uv和贴图，输出到outputs文件夹。



