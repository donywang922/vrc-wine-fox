# 加载 .NET 图形处理程序集
Add-Type -AssemblyName System.Drawing

# ================= 配置区 =================
$inputFolder = ".\"   # 输入文件夹（请替换为你的实际源图片路径）
$outputFolder = ".\Output" # 输出文件夹（单独的文件夹存放结果）
$maxSize = 128             # 最大分辨率 128x128
# ==========================================

# 如果输出文件夹不存在则创建
if (-not (Test-Path $outputFolder)) {
    New-Item -ItemType Directory -Path $outputFolder | Out-Null
}

# 筛选常见的图片格式文件
$images = Get-ChildItem -Path $inputFolder -File | Where-Object { $_.Extension -match '(?i)\.(jpg|jpeg|png|bmp|gif)$' }

if ($images.Count -eq 0) {
    Write-Host "未在 $inputFolder 中找到任何图片！" -ForegroundColor Yellow
    exit
}

foreach ($file in $images) {
    # 加载图片
    $img = [System.Drawing.Image]::FromFile($file.FullName)
    
    # 确定正方形的边长（取宽度和高度中较小的一边）
    $side = [math]::Min($img.Width, $img.Height)
    
    $x = 0
    $y = 0
    
    # 确定裁剪起点坐标 (X, Y)
    if ($img.Width -gt $img.Height) {
        # 横图：左右居中裁剪
        $x = [Math]::Floor(($img.Width - $side) / 2)
    } elseif ($img.Height -gt $img.Width) {
        # 竖图：非正方形图片裁最下面
        # 如果你的意思是【保留底部画面】，使用以下代码（已启用）：
        # $y = $img.Height - $side 
        
        # 如果你的意思是【裁掉底部（保留顶部画面）】，请注释掉上一行，取消下方代码的注释：
        $y = 0
    }

    # 第一步：根据坐标截取正方形区域
    $cropped = New-Object System.Drawing.Bitmap $side, $side
    $g = [System.Drawing.Graphics]::FromImage($cropped)
    $sourceRect = New-Object System.Drawing.Rectangle $x, $y, $side, $side
    $destRect = New-Object System.Drawing.Rectangle 0, 0, $side, $side
    $g.DrawImage($img, $destRect, $sourceRect, [System.Drawing.GraphicsUnit]::Pixel)

    # 第二步：将正方形缩放为“至多 128*128”
    # 如果原图短边本身就小于128，则保留原尺寸；否则缩小到 128
    $targetSide = [math]::Min($side, $maxSize)
    $finalImg = New-Object System.Drawing.Bitmap $targetSide, $targetSide
    $gFinal = [System.Drawing.Graphics]::FromImage($finalImg)
    # 设置高质量缩放模式以防图片模糊
    $gFinal.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $gFinal.DrawImage($cropped, 0, 0, $targetSide, $targetSide)

    # 第三步：输出保存
    $outputPath = Join-Path $outputFolder $file.Name
    $finalImg.Save($outputPath, $img.RawFormat)

    # 释放内存，解除对原文件的占用
    $gFinal.Dispose()
    $finalImg.Dispose()
    $g.Dispose()
    $cropped.Dispose()
    $img.Dispose()
    
    Write-Host "已处理: $($file.Name) -> $targetSide x $targetSide" -ForegroundColor Cyan
}

Write-Host "所有图片处理完成！已输出至: $outputFolder" -ForegroundColor Green