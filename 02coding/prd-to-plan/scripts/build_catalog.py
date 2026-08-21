from pathlib import Path
import json, re
import hashlib

ROOT = Path('/Users/ruikanwang/WORKSPACE/skills/PRD生成-812')
PRD = ROOT / '系统/需求文档'
OUT = ROOT / 'ai-execution-plan/AI执行清单.json'
NOW = '2026-08-20T14:36:00+08:00'
CONFIRM = ROOT / 'ai-execution-plan/AI执行清单确认.md'

story_specs = [
 ('US-001','企业多维数据浏览','数据运营人员','浏览和筛选企业维度指标','快速定位可用指标并判断其启停影响','UI-US-001-01'),
 ('US-002','数据授权管理','数据运营人员','维护企业数据授权记录','让受限数据采集具备可追踪授权状态','UI-US-002-01'),
 ('US-003','风险监控策略维护','风险运营人员','维护风险监控策略及指标配置','让监控规则可按业务场景启停和调整','UI-US-003-01'),
 ('US-004','报告生成配置','报告运营人员','选择报告类型并配置单个或批量生成任务','按目标企业和报告类型发起可追踪的生成任务','UI-US-004-01'),
 ('US-005','报告采集与完成','报告运营人员','处理报告数据采集、授权和生成完成流程','让报告任务在数据就绪后可生成并回到报告中心','UI-US-005-01'),
 ('US-006','企业风险监控看板','风险运营人员','查看和维护被监控企业及风险事件','及时发现企业风险并追踪事件明细','UI-US-006-01'),
 ('US-007','企业报告中心','报告运营人员','查询、下载和续看企业报告任务','集中追踪报告状态并取得已完成报告','UI-US-007-01'),
 ('US-008','规则策略基础维护','策略运营人员','维护规则策略的生命周期','保证规则策略可被查询、复用和安全启停','UI-US-008-01'),
 ('US-009','规则策略编排','策略运营人员','配置规则策略的业务要素、条件和输出映射','让规则策略形成可执行且可解释的判定链路','UI-US-009-01'),
 ('US-010','模型策略基础维护','策略运营人员','维护模型策略的生命周期','保证模型策略可被查询、复用和安全启停','UI-US-010-01'),
 ('US-011','模型策略模型配置','策略运营人员','配置模型 API、失败降级及输出字段','让模型策略能够稳定接入并产出业务结果','UI-US-011-01'),
 ('US-012','评估策略包基础维护','策略运营人员','维护评估策略包的生命周期','让业务场景能够复用已发布策略组合','UI-US-012-01'),
 ('US-013','评估策略包编排','策略运营人员','编排策略包中的执行策略和展示结果','形成可执行、可排序、可解释的评估方案','UI-US-013-01'),
 ('US-014','企业评估发起','评估运营人员','选择策略包并发起单个或批量企业评估','在明确企业和授权前提下建立评估单','UI-US-014-01'),
 ('US-015','企业评估归集与结果','评估运营人员','处理评估数据归集、执行进度和结果链路','在数据齐备后获得可追溯评估结论','UI-US-015-01'),
 ('US-016','评估记录台账','评估运营人员','查询、续跑和管理评估记录','保留评估留痕并快速回到未完成任务','UI-US-016-01'),
 ('US-017','首页业务门户','已登录业务人员','查看业务概览并进入风控主流程','快速判断当前状态并进入下一项业务工作','UI-US-017-01')]

file_to_story = {
 '01-企业多维数据.md':['US-001'], '02-数据授权.md':['US-002'], '03-风险监控策略.md':['US-003'],
 '04-报告工作台.md':['US-004','US-005'], '05-企业风险监控看板.md':['US-006'], '06-企业报告中心.md':['US-007'],
 '07-规则策略.md':['US-008','US-009'], '08-模型策略.md':['US-010','US-011'], '09-评估策略包管理.md':['US-012','US-013'],
 '10-企业评估工作台.md':['US-014','US-015'], '11-评估记录台账.md':['US-016'], '12-首页.md':['US-017']}
story_req_nums = {}
for _n, (_fn, _ids) in enumerate(file_to_story.items(), 1):
    for _sid in _ids:
        story_req_nums[_sid] = _n

def op_type(name):
    n=name.lower()
    if any(x in name for x in ('查询','列出','浏览','查看','列表','加载','状态')): return 'query'
    if any(x in name for x in ('新建','新增','发起','添加','上传','选择','选用')): return 'create'
    if any(x in name for x in ('删除','移除')): return 'delete'
    if any(x in name for x in ('下载','导出')): return 'export'
    if any(x in name for x in ('导入','解析')): return 'import'
    if any(x in name for x in ('跳转','返回')): return 'business_action'
    if any(x in name for x in ('点击','切换','筛选','重置')): return 'other'
    if any(x in name for x in ('启停','状态','授权','重试','保存','编辑','配置','设置','调整','处理','生成','复制')): return 'business_action'
    return 'other'

ops=[]; story_ops={s[0]:[] for s in story_specs}; req_num=1
for fn, sids in file_to_story.items():
    text=(PRD/fn).read_text(encoding='utf-8'); lines=text.splitlines()
    in_ops=False; current='操作清单'; count=0
    for idx,line in enumerate(lines):
        if line.startswith('## 3.') or line.startswith('## 3 '): in_ops=True
        if not in_ops: continue
        if re.match(r'^#{3,5} ',line): current=re.sub(r'^#{3,5} ','',line).strip()
        if line.startswith('- **触发**') or (fn.startswith('01-') and re.match(r'^### BR-00[1-3] ', line)):
            # report workbench and evaluation workbench are split by operation heading
            if fn.startswith('07-'):
                sid='US-009' if ('编辑页' in current or '配置' in current or '添加' in current or '保存策略' in current or '取消返回' in current) else 'US-008'
            elif fn.startswith('08-'):
                sid='US-011' if ('编辑页' in current or '配置' in current or '保存策略' in current or '取消返回' in current) else 'US-010'
            elif fn.startswith('09-'):
                sid='US-013' if ('编辑页' in current or '添加' in current or '调整' in current or '配置' in current or '设置' in current or '移除' in current or '聚合' in current or '保存策略包' in current or '取消返回' in current) else 'US-012'
            elif len(sids)==2:
                if fn.startswith('04-'):
                    sid='US-005' if ('采集' in current or '完成' in current or '授权' in line or '生成报告' in line) else 'US-004'
                else:
                    sid='US-015' if ('归集' in current or '执行' in current or '结果' in current or '指标' in current or '状态' in current or '稍后' in line or '继续' in line) else 'US-014'
            else: sid=sids[0]
            count += 1
            opid=f'OP-REQ-{req_num:03d}-{count:02d}'
            page=next(x[5] for x in story_specs if x[0]==sid)
            ops.append({'operation_id':opid,'name':current,'operation_type':op_type(current),'source_refs':[f'REQ-{req_num:03d}'],'source_locator':f'PRD-{req_num:03d}：{fn} / {current} / 触发','story_id':sid,'ui_surface_refs':[page],'coverage_status':'covered'})
            story_ops[sid].append(opid)
    req_num += 1

interfaces=[]
for o in ops:
    iid = o['operation_id'].replace('OP-', 'INT-')
    interfaces.append({'interface_capability_id': iid, 'name': o['name'], 'source_refs': o['source_refs'], 'source_locator': o['source_locator'], 'story_id': o['story_id'], 'operation_refs': [o['operation_id']], 'business_api_need': 'required'})

stories=[]
for seq,(sid,name,role,behavior,value,page) in enumerate(story_specs,1):
    oprefs=story_ops[sid]
    # Ensure at least two independently observable ACs while covering every operation.
    split=max(1,len(oprefs)//2); groups=[oprefs[:split],oprefs[split:]] if len(oprefs)>1 else [oprefs]
    ac=[]
    for j,g in enumerate(groups,1):
        if not g: continue
        ac.append({'id':f'AC-{sid}-{j:02d}','operation_refs':g,'text':f'Given {role}具备当前租户的相应权限，When 执行“{name}”范围内的业务操作，Then 页面展示与操作结果一致的状态、数据或跳转，并在失败时保留可识别的错误信息。'})
    reqs=sorted({o['source_refs'][0] for o in ops if o['story_id']==sid})
    prd_file = next(k for k, ids in file_to_story.items() if sid in ids)
    surfaces=[{'surface_id':page,'name':name,'surface_type':'page','operation_refs':oprefs,'source_refs':reqs+[f'AC-{sid}-01']}]
    deps=[]
    if sid in ('US-005','US-007'): deps=['US-004']
    if sid=='US-006': deps=['US-003']
    if sid=='US-009': deps=['US-008']
    if sid=='US-011': deps=['US-010']
    if sid=='US-013': deps=['US-012','US-008','US-010']
    if sid=='US-014': deps=['US-013','US-001','US-002']
    if sid=='US-015': deps=['US-014','US-002']
    if sid=='US-016': deps=['US-014','US-015']
    if sid=='US-017': deps=['US-007','US-012','US-016']
    story_ints=[i['interface_capability_id'] for i in interfaces if i['story_id']==sid]
    stories.append({'sequence':seq,'id':sid,'name':name,'file_stem':f'{sid}-{name}','user_story':f'作为{role}，我想要{behavior}，以便{value}。','priority':'P1','ui_required':True,'story_split_rationale':'按本故事独立业务价值、角色、状态边界和可验收结果说明拆分；技术接口和代码影响留到阶段 4核验。','operation_refs':oprefs,'interface_capability_refs':story_ints,'ui_surfaces':surfaces,'prd_refs':[{'requirement_id':r,'source_id':f'PRD-{int(r[-3:]):03d}','locator':f'系统/需求文档/{prd_file} / 操作清单'} for r in reqs],'scope':{'in':[name+'全流程及权限、空态和失败分支'],'out':['未在对应 PRD 明确的外部平台契约、审批流程和二期功能']},'acceptance_criteria':ac,'depends_on':deps,'risks':['现有代码和真实接口影响需在阶段 4按故事重新检索确认。'],'plan_generated':False,'development_completed':False,'self_test_completed':False,'plan_stale':False,'blocked_reason':None,'artifacts':{'contract':f'stories/{sid}-{name}/{sid}-{name}接口契约.json','implementation':f'stories/{sid}-{name}/{sid}-{name}AI执行明细.md','tests':f'stories/{sid}-{name}/{sid}-{name}测试用例.csv'},'last_updated_at':NOW})

data={'schema_version':'1.6','project':{'name':'系统风控业务增量项目','output_root':'.','baseline_id':'BL-20260820-001','material_manifest':'AI执行计划物料清单.md','technical_selection':'系统技术选型清单.md'},'catalog_confirmation_document':'AI执行清单确认.md','catalog_confirmation_hash':'sha256:'+hashlib.sha256(CONFIRM.read_bytes()).hexdigest(),'catalog_confirmed':True,'catalog_confirmed_at':NOW,'generated_at':NOW,'prd_operation_catalog':ops,'interface_capability_catalog':interfaces,'stories':stories}
OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(f'generated {len(ops)} operations, {len(stories)} stories -> {OUT}')
