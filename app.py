import streamlit as st
import random
import math

# --- 1. APP CONFIG ---
st.set_page_config(page_title="Factory Optimizer", layout="wide")
st.title("⚙️ Universal Press planner")

# --- 2. INPUT PANEL (Sidebar & Top) ---
with st.sidebar:
    st.header("🏁 Global Strategy")
    ITERATIONS = st.number_input("Search Iterations", value=1000000, step=50000, help="Higher = better results, but slower.")
    TARGET_PARTS_PER_OP = st.number_input("Target PPH Per Operator", value=300, help="Calculator tries to achieve first target per operator after that tries to optimize machine optimization.")

    st.divider()
    st.header("🚶 Physical Constraints")
    WALK_TIME = st.number_input("Walk Time per Press (s)", value=3)
    PARTS_PER_PRESS = st.number_input("Parts Produced per Press Cycle", value=2)

    st.divider()
    st.header("🏢 Line Capacities")
    st.caption("Max number of presses each line/operator can handle")
    cap1 = st.number_input("Line 1 Capacity", value=28)
    cap2 = st.number_input("Line 2 Capacity", value=28)
    cap3 = st.number_input("Line 3 Capacity", value=16)
    LINE_CAPACITIES = {1: cap1, 2: cap2, 3: cap3}
    NUM_LINES = len(LINE_CAPACITIES)

# --- 3. MATERIAL INPUTS ---
st.subheader("📦 Material & Machine Data")
st.info("Set 'Min Util (%)' for each mold. Set to 0 for filler molds so they can run at low utilization without penalty. Planner prioritizes achieving target operator PPH, set high for productivity, set low for production")

# Default data with Min Util (%) per mold
default_mats = [
    {'id': 'M01', 'qty': 10, 'p': 180, 'l': 4, 'min_util': 75.0},
    {'id': 'M02', 'qty': 16, 'p': 300, 'l': 8, 'min_util': 75.0},
    {'id': 'M03', 'qty': 4,  'p': 220, 'l': 5, 'min_util': 0.0},  # Filler Mold
    {'id': 'M04', 'qty': 0,  'p': 0,   'l': 0, 'min_util': 0.0},
    {'id': 'M05', 'qty': 0,  'p': 0,   'l': 0, 'min_util': 0.0},
    {'id': 'M06', 'qty': 0,  'p': 0,   'l': 0, 'min_util': 0.0},
    {'id': 'M07', 'qty': 0,  'p': 0,   'l': 0, 'min_util': 0.0},
    {'id': 'M08', 'qty': 0,  'p': 0,   'l': 0, 'min_util': 0.0},
    {'id': 'M09', 'qty': 0,  'p': 0,   'l': 0, 'min_util': 0.0},
    {'id': 'M10', 'qty': 0,  'p': 0,   'l': 0, 'min_util': 0.0},
]

# Interactive spreadsheet with per-mold min_util settings
edited_mats = st.data_editor(
    default_mats,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "id": "Material ID",
        "qty": "Quantity",
        "p": "Press Time (P)",
        "l": "Load Time (L)",
        "min_util": st.column_config.NumberColumn(
            "Min Util (%)",
            help="Minimum required mold utilization. Set to 0 for filler molds.",
            min_value=0.0,
            max_value=100.0,
            step=5.0
        )
    }
)

# Process the table into the list used by the algorithm
all_mats = []
for m in edited_mats:
    if m.get('qty', 0) > 0:
        for _ in range(int(m['qty'])):
            all_mats.append(m)

# --- 4. CORE LOGIC ---
def evaluate_plan(plan):
    total_factory_output = 0
    op_results = []

    for line_idx in range(NUM_LINES):
        line_items = plan[line_idx]
        if not line_items: continue

        physical_press_count = len(line_items)
        total_walking_in_lap = physical_press_count * WALK_TIME
        total_loading_in_lap = sum(it['l'] for it in line_items)
        active_work = total_walking_in_lap + total_loading_in_lap

        max_machine_needs = max([it['p'] + it['l'] for it in line_items])
        target_cycle = max(active_work, max_machine_needs)

        op_prod = 0
        total_m_util = 0
        press_details = []

        for it in line_items:
            machine_min_cycle = it['p'] + it['l']
            laps_needed = math.ceil(round(machine_min_cycle / target_cycle, 6))
            actual_visit_interval = laps_needed * target_cycle

            press_output = (3600 / actual_visit_interval) * PARTS_PER_PRESS
            op_prod += press_output
            m_util = ((it['p'] + it['l']) / actual_visit_interval) * 100
            total_m_util += m_util

            press_details.append({
                'id': it['id'], 
                'p': it['p'], 
                'l': it['l'],
                'min_util': it.get('min_util', 0.0),
                'rounds': laps_needed, 
                'util': m_util, 
                'out_hr': press_output
            })

        op_results.append({
            'line_num': line_idx + 1,
            'output': op_prod,
            'avg_m_util': total_m_util / len(line_items),
            'active_loop': active_work,
            'total_cycle': target_cycle,
            'count': len(line_items),
            'details': press_details,
            'op_use': (active_work / target_cycle) * 100
        })
        total_factory_output += op_prod

    return op_results, total_factory_output

# --- 5. EXECUTION ---
if st.button('🚀 Run Optimizer with Current Settings'):
    if not all_mats:
        st.warning("No materials to process. Please add items to the table.")
    else:
        best_plan = None
        best_score = -float('inf')

        progress_bar = st.progress(0)

        # The Search Loop
        for i in range(ITERATIONS):
            if i % (max(1, ITERATIONS // 10)) == 0:
                progress_bar.progress(i / ITERATIONS)

            shuffled = all_mats[:]
            random.shuffle(shuffled)
            current_plan = [[] for _ in range(NUM_LINES)]

            for m in shuffled:
                available = [l for l in range(NUM_LINES) if len(current_plan[l]) < LINE_CAPACITIES[l+1]]
                if not available: break
                target_line = random.choice(available)
                current_plan[target_line].append(m)

            res, total_out = evaluate_plan(current_plan)
            if res:
                num_ops = len(res)
                score = 0
                all_met_target = True
                utilization_valid = True

                for op in res:
                    # Check operator target output
                    if op['output'] < TARGET_PARTS_PER_OP:
                        all_met_target = False
                        score -= (TARGET_PARTS_PER_OP - op['output']) * 1000
                    else:
                        score += 5000

                    # Check individual mold utilization constraint
                    for press in op['details']:
                        min_req = press['min_util']
                        if press['util'] < min_req:
                            utilization_valid = False
                            score -= (min_req - press['util']) * 2000

                if all_met_target and utilization_valid:
                    score += sum(op['avg_m_util'] for op in res) * 100
                    score += (total_out / num_ops) * 10

                if score > best_score:
                    best_score = score
                    best_plan = res

        progress_bar.empty()

        # --- RESULTS DISPLAY ---
        if best_plan:
            final_total = sum(o['output'] for o in best_plan)
            final_ops = len(best_plan)

            st.success(f"Best Configuration Found in {ITERATIONS:,} iterations")

            col1, col2, col3 = st.columns(3)
            col1.metric("Total Factory PPH", f"{final_total:.1f}")
            col2.metric("Active Operators", final_ops)
            col3.metric("Avg PPH/Op", f"{final_total/final_ops:.1f}")

            for op in best_plan:
                with st.expander(f"📋 LINE {op['line_num']} - Output: {op['output']:.1f} PPH", expanded=True):
                    c_a, c_b, c_c = st.columns(3)
                    c_a.write(f"**Operator Utilization:** {op['op_use']:.1f}%")
                    c_b.write(f"**Average Machine Uptime:** {op['avg_m_util']:.1f}%")
                    c_c.write(f"**Calculated Pace:** {op['total_cycle']}s")
                    st.table(op['details'])
        else:
            st.error("Could not find a valid plan. Check your capacities vs quantities.")
