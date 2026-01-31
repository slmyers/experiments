"""
Query plan visualizer using Graphviz.

Generates tree diagrams from EXPLAIN JSON output and produces
side-by-side baseline vs bloated comparisons.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

sys.path.insert(0, str(__file__).rsplit("/", 3)[0])
from common import PLANS_DIR


@dataclass
class PlanNode:
    """Represents a node in the query plan tree."""
    node_type: str
    relation_name: Optional[str] = None
    alias: Optional[str] = None
    startup_cost: float = 0.0
    total_cost: float = 0.0
    plan_rows: int = 0
    plan_width: int = 0
    actual_startup_time: float = 0.0
    actual_total_time: float = 0.0
    actual_rows: int = 0
    actual_loops: int = 1
    shared_hit_blocks: int = 0
    shared_read_blocks: int = 0
    index_name: Optional[str] = None
    index_cond: Optional[str] = None
    filter: Optional[str] = None
    rows_removed_by_filter: int = 0
    children: List["PlanNode"] = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []
    
    @property
    def row_estimate_error(self) -> float:
        """Ratio of actual to estimated rows."""
        if self.plan_rows == 0:
            return float('inf') if self.actual_rows > 0 else 1.0
        return self.actual_rows / self.plan_rows
    
    @property
    def time_per_row(self) -> float:
        """Average time per row in ms."""
        if self.actual_rows == 0:
            return 0.0
        return self.actual_total_time / self.actual_rows


def parse_plan_node(plan_dict: Dict[str, Any]) -> PlanNode:
    """Parse a plan dictionary into a PlanNode tree."""
    node = PlanNode(
        node_type=plan_dict.get("Node Type", "Unknown"),
        relation_name=plan_dict.get("Relation Name"),
        alias=plan_dict.get("Alias"),
        startup_cost=plan_dict.get("Startup Cost", 0.0),
        total_cost=plan_dict.get("Total Cost", 0.0),
        plan_rows=plan_dict.get("Plan Rows", 0),
        plan_width=plan_dict.get("Plan Width", 0),
        actual_startup_time=plan_dict.get("Actual Startup Time", 0.0),
        actual_total_time=plan_dict.get("Actual Total Time", 0.0),
        actual_rows=plan_dict.get("Actual Rows", 0),
        actual_loops=plan_dict.get("Actual Loops", 1),
        shared_hit_blocks=plan_dict.get("Shared Hit Blocks", 0),
        shared_read_blocks=plan_dict.get("Shared Read Blocks", 0),
        index_name=plan_dict.get("Index Name"),
        index_cond=plan_dict.get("Index Cond"),
        filter=plan_dict.get("Filter"),
        rows_removed_by_filter=plan_dict.get("Rows Removed by Filter", 0),
    )
    
    # Parse child nodes
    for child_dict in plan_dict.get("Plans", []):
        node.children.append(parse_plan_node(child_dict))
    
    return node


def node_to_graphviz_label(node: PlanNode) -> str:
    """Generate Graphviz label for a plan node."""
    lines = [f"<b>{node.node_type}</b>"]
    
    if node.relation_name:
        lines.append(f"<i>{node.relation_name}</i>")
    
    if node.index_name:
        lines.append(f"idx: {node.index_name}")
    
    # Cost and timing
    lines.append(f"cost: {node.total_cost:.1f}")
    lines.append(f"time: {node.actual_total_time:.2f}ms")
    
    # Rows with estimate accuracy
    estimate_error = node.row_estimate_error
    if 0.5 <= estimate_error <= 2.0:
        accuracy_color = "green"
    elif 0.1 <= estimate_error <= 10.0:
        accuracy_color = "orange"
    else:
        accuracy_color = "red"
    
    lines.append(f"rows: {node.actual_rows:,} (est: {node.plan_rows:,})")
    
    # Buffer stats
    total_blocks = node.shared_hit_blocks + node.shared_read_blocks
    if total_blocks > 0:
        hit_ratio = node.shared_hit_blocks / total_blocks
        lines.append(f"buffers: {total_blocks:,} ({hit_ratio:.0%} hit)")
    
    return "<br/>".join(lines)


def node_to_graphviz_color(node: PlanNode, baseline_node: Optional[PlanNode] = None) -> str:
    """Determine node color based on type and comparison."""
    # Default colors by node type
    type_colors = {
        "Seq Scan": "#ffcccc",      # Light red - often bad
        "Index Scan": "#ccffcc",     # Light green - usually good
        "Index Only Scan": "#ccffcc",
        "Bitmap Heap Scan": "#ffffcc",
        "Bitmap Index Scan": "#ffffcc",
        "Hash Join": "#cce5ff",
        "Merge Join": "#cce5ff",
        "Nested Loop": "#cce5ff",
        "Sort": "#e5ccff",
        "Aggregate": "#ffccff",
    }
    
    base_color = type_colors.get(node.node_type, "#f0f0f0")
    
    # Highlight changes from baseline
    if baseline_node:
        if node.node_type != baseline_node.node_type:
            return "#ff9999"  # Bright red - node type changed!
        
        # Significant performance regression
        if baseline_node.actual_total_time > 0:
            time_ratio = node.actual_total_time / baseline_node.actual_total_time
            if time_ratio > 2.0:
                return "#ffcc99"  # Orange - significant slowdown
    
    return base_color


def generate_graphviz_dot(
    node: PlanNode,
    baseline_node: Optional[PlanNode] = None,
    graph_name: str = "plan",
) -> str:
    """Generate Graphviz DOT representation of plan tree."""
    lines = [
        f'digraph {graph_name} {{',
        '  rankdir=TB;',
        '  node [shape=box, style="filled,rounded", fontname="Helvetica", fontsize=10];',
        '  edge [fontname="Helvetica", fontsize=9];',
        '',
    ]
    
    node_id = [0]  # Mutable counter
    
    def add_node(n: PlanNode, parent_id: Optional[int] = None, baseline_n: Optional[PlanNode] = None) -> int:
        current_id = node_id[0]
        node_id[0] += 1
        
        label = node_to_graphviz_label(n)
        color = node_to_graphviz_color(n, baseline_n)
        
        lines.append(f'  n{current_id} [label=<{label}>, fillcolor="{color}"];')
        
        if parent_id is not None:
            # Add edge with rows info
            edge_label = f"{n.actual_rows:,} rows"
            lines.append(f'  n{parent_id} -> n{current_id} [label="{edge_label}"];')
        
        # Process children
        baseline_children = baseline_n.children if baseline_n else []
        for i, child in enumerate(n.children):
            baseline_child = baseline_children[i] if i < len(baseline_children) else None
            add_node(child, current_id, baseline_child)
        
        return current_id
    
    add_node(node, baseline_n=baseline_node)
    
    lines.append('}')
    return '\n'.join(lines)


def render_plan_to_image(
    plan_data: Dict[str, Any],
    output_path: Path,
    baseline_plan: Optional[Dict[str, Any]] = None,
    format: str = "png",
) -> Path:
    """
    Render a query plan to an image file.
    
    Args:
        plan_data: The plan JSON data (output from EXPLAIN FORMAT JSON)
        output_path: Path for output image (without extension)
        baseline_plan: Optional baseline plan for comparison highlighting
        format: Output format (png, svg, pdf)
    
    Returns:
        Path to the generated image file
    """
    try:
        import pydot
    except ImportError:
        print("Warning: pydot not installed. Install with: pip install pydot")
        return None
    
    # Parse plans
    if isinstance(plan_data, list) and len(plan_data) > 0:
        plan_dict = plan_data[0].get("Plan", plan_data[0])
    else:
        plan_dict = plan_data.get("Plan", plan_data)
    
    node = parse_plan_node(plan_dict)
    
    baseline_node = None
    if baseline_plan:
        if isinstance(baseline_plan, list) and len(baseline_plan) > 0:
            baseline_dict = baseline_plan[0].get("Plan", baseline_plan[0])
        else:
            baseline_dict = baseline_plan.get("Plan", baseline_plan)
        baseline_node = parse_plan_node(baseline_dict)
    
    # Generate DOT
    dot_string = generate_graphviz_dot(node, baseline_node)
    
    # Render with pydot
    graphs = pydot.graph_from_dot_data(dot_string)
    if not graphs:
        print("Warning: Failed to parse DOT string")
        return None
    
    graph = graphs[0]
    output_file = output_path.with_suffix(f".{format}")
    
    if format == "png":
        graph.write_png(str(output_file))
    elif format == "svg":
        graph.write_svg(str(output_file))
    elif format == "pdf":
        graph.write_pdf(str(output_file))
    
    return output_file


def generate_comparison_image(
    baseline_plan: Dict[str, Any],
    current_plan: Dict[str, Any],
    output_path: Path,
    title: str = "Plan Comparison",
    format: str = "png",
) -> Path:
    """
    Generate side-by-side plan comparison image.
    
    Creates a single image with baseline and current plans
    highlighting differences.
    """
    try:
        import pydot
    except ImportError:
        print("Warning: pydot not installed")
        return None
    
    # Parse both plans
    def get_plan_dict(plan_data):
        if isinstance(plan_data, list) and len(plan_data) > 0:
            return plan_data[0].get("Plan", plan_data[0])
        return plan_data.get("Plan", plan_data)
    
    baseline_dict = get_plan_dict(baseline_plan)
    current_dict = get_plan_dict(current_plan)
    
    baseline_node = parse_plan_node(baseline_dict)
    current_node = parse_plan_node(current_dict)
    
    # Create combined graph with two subgraphs
    lines = [
        'digraph comparison {',
        '  rankdir=TB;',
        '  compound=true;',
        '  node [shape=box, style="filled,rounded", fontname="Helvetica", fontsize=10];',
        '  edge [fontname="Helvetica", fontsize=9];',
        f'  labelloc="t";',
        f'  label="{title}";',
        '',
        '  subgraph cluster_baseline {',
        '    label="Baseline";',
        '    style=dashed;',
        '    color=blue;',
    ]
    
    # Add baseline nodes
    node_id = [0]
    
    def add_node_to_subgraph(n: PlanNode, prefix: str, parent_id: Optional[str] = None) -> str:
        current_id = f"{prefix}_{node_id[0]}"
        node_id[0] += 1
        
        label = node_to_graphviz_label(n)
        color = node_to_graphviz_color(n)
        
        lines.append(f'    {current_id} [label=<{label}>, fillcolor="{color}"];')
        
        if parent_id:
            lines.append(f'    {parent_id} -> {current_id};')
        
        for child in n.children:
            add_node_to_subgraph(child, prefix, current_id)
        
        return current_id
    
    add_node_to_subgraph(baseline_node, "b")
    lines.append('  }')
    lines.append('')
    lines.append('  subgraph cluster_current {')
    lines.append('    label="Current (with bloat)";')
    lines.append('    style=dashed;')
    lines.append('    color=red;')
    
    node_id[0] = 0
    add_node_to_subgraph(current_node, "c")
    
    lines.append('  }')
    lines.append('}')
    
    dot_string = '\n'.join(lines)
    
    graphs = pydot.graph_from_dot_data(dot_string)
    if not graphs:
        return None
    
    graph = graphs[0]
    output_file = output_path.with_suffix(f".{format}")
    
    if format == "png":
        graph.write_png(str(output_file))
    elif format == "svg":
        graph.write_svg(str(output_file))
    
    return output_file


def load_plan_file(plan_path: Path) -> Dict[str, Any]:
    """Load a plan JSON file."""
    with open(plan_path, 'r') as f:
        return json.load(f)


def find_baseline_and_final_plans(
    plans_dir: Path,
    query_name: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Find baseline and final plan files for a query."""
    baseline = None
    final = None
    
    for plan_file in sorted(plans_dir.glob(f"{query_name}_*.json")):
        plan_data = load_plan_file(plan_file)
        snapshot_type = plan_data.get("snapshot_type", "")
        
        if snapshot_type == "baseline" and baseline is None:
            baseline = plan_data
        elif snapshot_type == "final":
            final = plan_data
    
    return baseline, final


def generate_all_comparisons(
    run_id: str,
    output_dir: Path = None,
    format: str = "png",
) -> List[Path]:
    """Generate comparison images for all queries in a run."""
    plans_dir = PLANS_DIR / run_id
    if output_dir is None:
        output_dir = plans_dir / "visuals"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    generated = []
    
    # Find unique query names
    query_names = set()
    for plan_file in plans_dir.glob("*.json"):
        # Extract query name from filename like "point_lookup_0001.json"
        name = plan_file.stem.rsplit("_", 1)[0]
        query_names.add(name)
    
    for query_name in sorted(query_names):
        baseline, final = find_baseline_and_final_plans(plans_dir, query_name)
        
        if baseline and final:
            # Generate comparison
            output_path = output_dir / f"{query_name}_comparison"
            result = generate_comparison_image(
                baseline_plan=baseline.get("plan", baseline),
                current_plan=final.get("plan", final),
                output_path=output_path,
                title=f"{query_name}: Baseline vs Bloated",
                format=format,
            )
            if result:
                generated.append(result)
                print(f"Generated: {result}")
            
            # Also generate individual plans
            baseline_path = output_dir / f"{query_name}_baseline"
            result = render_plan_to_image(
                baseline.get("plan", baseline),
                baseline_path,
                format=format,
            )
            if result:
                generated.append(result)
            
            final_path = output_dir / f"{query_name}_final"
            result = render_plan_to_image(
                final.get("plan", final),
                final_path,
                baseline_plan=baseline.get("plan", baseline),
                format=format,
            )
            if result:
                generated.append(result)
    
    return generated


def main():
    parser = argparse.ArgumentParser(description="Visualize query plans")
    parser.add_argument(
        "--run-id",
        required=True,
        help="Experiment run ID",
    )
    parser.add_argument(
        "--format",
        choices=["png", "svg", "pdf"],
        default="png",
        help="Output format (default: png)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: plans/<run_id>/visuals)",
    )
    
    args = parser.parse_args()
    
    print(f"Generating plan visualizations for run: {args.run_id}")
    
    generated = generate_all_comparisons(
        run_id=args.run_id,
        output_dir=args.output_dir,
        format=args.format,
    )
    
    print(f"\nGenerated {len(generated)} visualization(s)")


if __name__ == "__main__":
    main()
