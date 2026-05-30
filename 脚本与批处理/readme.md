##### 批处理脚本与处理后的模型



脚本完全由Gemini生成，未做任何修改。

提示词如下 \*由于个人记忆缘故，不保证可以重现



1. 现有如下项目结构。items文件夹，内部是n张来自Minecraft的物品的贴图，均为16\*16png。m1-m4四个黑白png，在项目根目录下，用于遮罩。我需要实现如下任务，给items文件夹中的物品生成obj模型，每个obj文件中包含由四个遮罩拆成4的四个网格体，黑色部分保留，模型的侧面uv应平铺覆盖相邻的整个像素。复制贴图到obj文件同级中，并且文件需要utf8编码。
2. 现在有，1. selected\_items文件夹，内部是刚刚生成的物品模型，2. objs文件夹，内部是blockbench导出的有特殊模型的物品的模型的obj文件。我需要如下功能，读取两个文件夹中的全部模型，获取它们uv所包含的像素，将这些面合并到一个贴图中，同时需要更新所有obj文件中的uv。将更新后的模型，合并的贴图和mtl输出到output文件夹中。注意 1. blockbench导出的obj有些会同时引用多个贴图。2. 最终输出的贴图边长应为2^n，可以不是正方形。3. 如果两个面引用的像素是相同的，不要在最终贴图中存两次。上方给items生成的obj中是包含4个网格体的，注意不要在合并后丢失这一信息。
3. 在wine\_fox文件夹中，存在一个模型文件main.json和n个动画文件\*.animation.json，附件为两个示例。我需要实现如下任务，1.合并所有动画文件，清理其中没有骨骼关键帧的动画，如果两个动画的关键帧相同，保留名字更短的那个。时间线，粒子，声音关键帧不影响是否清理。2.清理模型文件，对于每个组，a.如果这个组从未在动画中出现，就地解散，内部物件移动至该组的父级。b.如果这个组中只有另一个组且只有一个组在动画中出现过，将两个组合并，保留有动画的那个组。c.如果这个组中只有另一个组且两个组的偏移相同，将两个组合并，同时如果被删除的组在动画中出现，将其重定向到保留的组。将最终的模型和动画文件输出到wine\_fox\_out文件夹。
4. 在wine\_fox\_out文件夹中存在一个模型json和一个动画json，这是示例文件，我需要一个脚本做如下操作，如果guiroot中有动画，移动到root上，如果root上同时有动画，尝试叠加。如果mroot上有动画，尝试变换到root上（这两个组锚点不同）。



##### 结构

items/ -- 原始物品贴图文件

objs/ -- 有独立模型的物品经由blockbench导出的obj文件

output\_item\_models/ -- 由gen\_item\_models.py从items文件夹生成的物品模型obj文件

outputs/ -- 由merge\_objs.py对objs文件夹和select\_items文件夹中所有模型重排uv后的obj文件。

outputs\_simplified/ -- 由blender对output\_item\_models文件夹模型应用精简修改器后的obj文件。

selected\_items/ -- 部分outputs\_simplified中的模型被移动到此处，由于面数限制，不得不舍弃一些物品。

wine\_fox/ -- 酒狐的原始模型和动画文件。

wine\_fox\_out/ -- 由refactor\_wine\_fox.py清理后的模型和动画文件。

m1-4.png -- 生成物品模型时的遮罩，每个物品按照黑色部分拆分为四个网格体。

gen\_item\_models.py -- 为items文件夹中的图片生成物品模型，用m1-4作为遮罩拆分网格体。输出到output\_item\_models文件夹。

merge\_objs.py -- 合并objs文件夹和selected\_items文件夹中模型的uv和贴图，输出到outputs文件夹。

refactor\_wine\_fox.py -- 合并wine\_fox文件夹中酒狐模型的组与动画，输出到wine\_fox\_out文件夹。

