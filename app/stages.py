STAGES = (
    ('assay', '化验采信'), ('dry', '干物折算'), ('formula', '目标验方'), ('blend', '整数寻优'),
    ('stock', '领用余量'), ('batches', '留档复跑'), ('certificate', '试配签发'),
)
LABELS = dict(STAGES)
PLAN_FIELDS = {'as_of':'试配日期', 'target_g':'计划量 (g)', 'step_g':'领用刻度 (g)', 'dry_min_g':'干物下限 (g)',
               'gel_low_sag':'凝胶下限 (SAG)', 'gel_high_sag':'凝胶上限 (SAG)'}
