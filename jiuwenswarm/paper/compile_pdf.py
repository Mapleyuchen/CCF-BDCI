#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用Python生成PDF的替代方案
通过简化的LaTeX引擎或使用在线服务
"""

import subprocess
import os
import sys
from pathlib import Path

def find_pdflatex():
    """查找pdflatex可执行文件"""
    possible_paths = [
        r"C:\Program Files\MiKTeX\miktex\bin\x64\pdflatex.exe",
        r"C:\Users\fanqi\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe",
        r"C:\MiKTeX\miktex\bin\x64\pdflatex.exe",
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    # 尝试在PATH中查找
    try:
        result = subprocess.run(['where', 'pdflatex'],
                              capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
    except:
        pass

    return None

def compile_latex(tex_file, output_dir=None):
    """编译LaTeX文件"""
    tex_path = Path(tex_file)
    if not tex_path.exists():
        print(f"错误: {tex_file} 不存在")
        return False

    # 查找pdflatex
    pdflatex = find_pdflatex()
    if not pdflatex:
        print("错误: 找不到pdflatex")
        print("\n请使用以下方式之一:")
        print("1. 手动安装MiKTeX: https://miktex.org/download")
        print("2. 使用Overleaf在线编译: https://www.overleaf.com")
        return False

    print(f"找到pdflatex: {pdflatex}")

    # 切换到tex文件目录
    work_dir = tex_path.parent
    os.chdir(work_dir)

    # 编译（运行两次以确保引用正确）
    print(f"\n开始编译 {tex_path.name}...")

    for i in range(2):
        print(f"\n第 {i+1} 次编译...")
        try:
            result = subprocess.run(
                [pdflatex, '-interaction=nonstopmode', tex_path.name],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                print("编译出错！")
                print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
                return False
            else:
                print(f"✓ 第 {i+1} 次编译成功")
        except subprocess.TimeoutExpired:
            print("编译超时！")
            return False
        except Exception as e:
            print(f"编译失败: {e}")
            return False

    # 检查PDF是否生成
    pdf_file = tex_path.with_suffix('.pdf')
    if pdf_file.exists():
        print(f"\n✓ PDF生成成功: {pdf_file}")
        print(f"  文件大小: {pdf_file.stat().st_size / 1024:.1f} KB")
        return True
    else:
        print("\n✗ PDF文件未生成")
        return False

if __name__ == "__main__":
    # 编译paper.tex
    paper_dir = Path(__file__).parent
    tex_file = paper_dir / "paper.tex"

    if compile_latex(tex_file):
        print("\n🎉 论文编译完成！")
    else:
        print("\n❌ 编译失败，请查看错误信息")
        sys.exit(1)
