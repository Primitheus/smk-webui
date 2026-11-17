$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$asset = Join-Path $PSScriptRoot '../src/smk_webui/web/icon.svg'
[xml]$svg = Get-Content -LiteralPath $asset -Raw
$rect = $svg.svg.rect
$shape = $svg.svg.path
$numbers = [regex]::Matches($shape.d, '-?\d+(?:\.\d+)?') | ForEach-Object { [single]$_.Value }
$frames = @()
foreach ($size in @(16,24,32,48,64,128,256)) {
    $bitmap = [Drawing.Bitmap]::new($size,$size)
    $graphics = [Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.ScaleTransform($size/128.0,$size/128.0)
    $outline = [Drawing.Drawing2D.GraphicsPath]::new()
    $x=[single]$rect.x; $y=[single]$rect.y; $width=[single]$rect.width; $height=[single]$rect.height; $diameter=2*[single]$rect.rx
    $outline.AddArc($x,$y,$diameter,$diameter,180,90)
    $outline.AddArc($x+$width-$diameter,$y,$diameter,$diameter,270,90)
    $outline.AddArc($x+$width-$diameter,$y+$height-$diameter,$diameter,$diameter,0,90)
    $outline.AddArc($x,$y+$height-$diameter,$diameter,$diameter,90,90)
    $outline.CloseFigure()
    $brush=[Drawing.SolidBrush]::new([Drawing.ColorTranslator]::FromHtml($rect.fill))
    $pen=[Drawing.Pen]::new([Drawing.Color]::White,[single]$rect.'stroke-width')
    $graphics.FillPath($brush,$outline); $graphics.DrawPath($pen,$outline)
    $letter=[Drawing.Drawing2D.GraphicsPath]::new()
    $px=$numbers[0];$py=$numbers[1]
    for($i=2;$i -lt $numbers.Count;$i+=6) {
        $letter.AddBezier($px,$py,$numbers[$i],$numbers[$i+1],$numbers[$i+2],$numbers[$i+3],$numbers[$i+4],$numbers[$i+5])
        $px=$numbers[$i+4];$py=$numbers[$i+5]
    }
    $pen.Width=[single]$shape.'stroke-width';$pen.StartCap='Round';$pen.EndCap='Round'
    $graphics.DrawPath($pen,$letter)
    $stream=[IO.MemoryStream]::new();$bitmap.Save($stream,[Drawing.Imaging.ImageFormat]::Png)
    $frames+=,@{Size=$size;Bytes=$stream.ToArray()}
    $stream.Dispose();$letter.Dispose();$pen.Dispose();$brush.Dispose();$outline.Dispose();$graphics.Dispose();$bitmap.Dispose()
}
$output=[IO.File]::Create((Join-Path $PSScriptRoot '../src/smk_webui/web/icon.ico'))
$writer=[IO.BinaryWriter]::new($output)
try {
    $writer.Write([uint16]0);$writer.Write([uint16]1);$writer.Write([uint16]$frames.Count)
    $offset=6+16*$frames.Count
    foreach($frame in $frames) {
        $dimension=if($frame.Size -eq 256){0}else{$frame.Size}
        $writer.Write([byte]$dimension);$writer.Write([byte]$dimension);$writer.Write([uint16]0)
        $writer.Write([uint16]1);$writer.Write([uint16]32)
        $writer.Write([uint32]$frame.Bytes.Length);$writer.Write([uint32]$offset)
        $offset+=$frame.Bytes.Length
    }
    foreach($frame in $frames){$writer.Write([byte[]]$frame.Bytes)}
} finally {$writer.Dispose();$output.Dispose()}
