#!/usr/bin/env python3
# coding: utf-8
"""
结果对比分析脚本
对比基线系统和增强系统的实验结果
"""

import json
import sys
from pathlib import Path
from typing import Dict, List
import statistics


def load_results(filepath: str) -> List[Dict]:
    """加载实验结果"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def group_by_task_type(results: List[Dict]) -> Dict[str, List[Dict]]:
    """按任务类型分组"""
    grouped = {}
    for result in results:
        task_type = result['task_type']
        if task_type not in grouped:
            grouped[task_type] = []
        grouped[task_type].append(result)
    return grouped


def calculate_statistics(results: List[Dict], metric: str) -> Dict:
    """计算统计信息"""
    values = [r['metrics'][metric] for r in results if metric in r['metrics']]

    if not values:
        return {"mean": 0, "std": 0, "min": 0, "max": 0}

    return {
        "mean": statistics.mean(values),
        "std": statistics.stdev(values) if len(values) > 1 else 0,
        "min": min(values),
        "max": max(values)
    }


def compare_systems(baseline_file: str, enhanced_file: str):
    """对比两个系统的性能"""

    print("="*70)
    print("系统性能对比分析")
    print("="*70)

    # 加载数据
    baseline_results = load_results(baseline_file)
    enhanced_results = load_results(enhanced_file)

    # 按任务类型分组
    baseline_grouped = group_by_task_type(baseline_results)
    enhanced_grouped = group_by_task_type(enhanced_results)

    # 定义要对比的指标
    metrics_by_task = {
        "single_turn": ["accuracy", "precision", "recall", "f1_score", "response_time"],
        "multi_step": ["completion_rate", "coherence_score", "response_time"],
        "cross_session": ["retention_rate", "consistency_score", "response_time"],
        "team_collaboration": ["sharing_efficiency", "collaboration_quality", "sync_overhead"]
    }

    comparison_results = {}

    # 对比每种任务类型
    for task_type in baseline_grouped.keys():
        print(f"\n{'='*70}")
        print(f"任务类型: {task_type}")
        print(f"{'='*70}")

        baseline_tasks = baseline_grouped[task_type]
        enhanced_tasks = enhanced_grouped.get(task_type, [])

        if not enhanced_tasks:
            print("  增强系统无此类型任务")
            continue

        comparison_results[task_type] = {}

        # 对比每个指标
        metrics = metrics_by_task.get(task_type, [])

        for metric in metrics:
            baseline_stats = calculate_statistics(baseline_tasks, metric)
            enhanced_stats = calculate_statistics(enhanced_tasks, metric)

            if baseline_stats["mean"] == 0:
                continue

            # 计算提升百分比
            improvement = ((enhanced_stats["mean"] - baseline_stats["mean"]) /
                          baseline_stats["mean"] * 100)

            comparison_results[task_type][metric] = {
                "baseline": baseline_stats,
                "enhanced": enhanced_stats,
                "improvement_pct": improvement
            }

            # 打印对比
            print(f"\n{metric}:")
            print(f"  基线系统: {baseline_stats['mean']:.4f} (±{baseline_stats['std']:.4f})")
            print(f"  增强系统: {enhanced_stats['mean']:.4f} (±{enhanced_stats['std']:.4f})")

            if improvement > 0:
                print(f"  提升: +{improvement:.2f}%")
            else:
                print(f"  变化: {improvement:.2f}%")

    # 总体汇总
    print(f"\n{'='*70}")
    print("总体性能提升汇总")
    print(f"{'='*70}")

    all_improvements = []
    for task_type, metrics in comparison_results.items():
        for metric, data in metrics.items():
            if metric != "response_time" and metric != "sync_overhead":
                all_improvements.append(data["improvement_pct"])

    if all_improvements:
        avg_improvement = statistics.mean(all_improvements)
        print(f"\n平均性能提升: {avg_improvement:.2f}%")
        print(f"最大提升: {max(all_improvements):.2f}%")
        print(f"最小提升: {min(all_improvements):.2f}%")

    # 保存对比结果
    output_dir = Path("experiments/comparison")
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "comparison.json", 'w', encoding='utf-8') as f:
        json.dump(comparison_results, f, ensure_ascii=False, indent=2)

    print(f"\n对比结果已保存到: {output_dir / 'comparison.json'}")

    return comparison_results


def generate_latex_table(comparison_results: Dict):
    """生成LaTeX表格"""

    output_dir = Path("experiments/comparison")
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "results_table.tex", 'w', encoding='utf-8') as f:
        f.write("\\begin{table}[h]\n")
        f.write("\\centering\n")
        f.write("\\caption{Performance Comparison: Baseline vs. Enhanced System}\n")
        f.write("\\label{tab:performance}\n")
        f.write("\\begin{tabular}{lcccc}\n")
        f.write("\\hline\n")
        f.write("Task Type & Metric & Baseline & Enhanced & Improvement \\\\\n")
        f.write("\\hline\n")

        for task_type, metrics in comparison_results.items():
            first_metric = True
            for metric, data in metrics.items():
                baseline = data["baseline"]["mean"]
                enhanced = data["enhanced"]["mean"]
                improvement = data["improvement_pct"]

                task_label = task_type.replace("_", " ").title() if first_metric else ""
                metric_label = metric.replace("_", " ").title()

                # 格式化数值
                if metric.endswith("_rate") or metric == "accuracy":
                    baseline_str = f"{baseline:.1%}"
                    enhanced_str = f"{enhanced:.1%}"
                elif metric == "response_time":
                    baseline_str = f"{baseline:.2f}s"
                    enhanced_str = f"{enhanced:.2f}s"
                else:
                    baseline_str = f"{baseline:.2f}"
                    enhanced_str = f"{enhanced:.2f}"

                improvement_str = f"+{improvement:.1f}\\%" if improvement > 0 else f"{improvement:.1f}\\%"

                f.write(f"{task_label} & {metric_label} & {baseline_str} & {enhanced_str} & {improvement_str} \\\\\n")

                first_metric = False

            f.write("\\hline\n")

        f.write("\\end{tabular}\n")
        f.write("\\end{table}\n")

    print(f"LaTeX表格已生成: {output_dir / 'results_table.tex'}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="对比实验结果")
    parser.add_argument("--baseline", type=str,
                       default="experiments/baseline/results.json",
                       help="基线系统结果文件")
    parser.add_argument("--enhanced", type=str,
                       default="experiments/enhanced/results.json",
                       help="增强系统结果文件")

    args = parser.parse_args()

    # 执行对比
    comparison_results = compare_systems(args.baseline, args.enhanced)

    # 生成LaTeX表格
    generate_latex_table(comparison_results)

    print("\n分析完成！")


if __name__ == "__main__":
    main()
