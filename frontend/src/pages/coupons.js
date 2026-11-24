        import {workspace} from '../workspace.js';
        import {el} from '../dom.js';

        const page = {
  "title": "冷却后的尺规测量",
  "module": "温区试片",
  "caption": "温区试片",
  "detail": "同一试片记录片厚、温区、目标与实测。复核员确认后才进入拟合，验证试片独立留出。",
  "path": "/coupons",
  "columns": [
    {
      "name": "code",
      "label": "编号"
    },
    {
      "name": "jig",
      "label": "弯模"
    },
    {
      "name": "heat",
      "label": "保温温度 °C"
    },
    {
      "name": "thick",
      "label": "片厚 mm"
    },
    {
      "name": "target",
      "label": "目标弯度 mm"
    },
    {
      "name": "measured",
      "label": "冷却弯度 mm"
    },
    {
      "name": "measured_original",
      "label": "原始读数 mm"
    },
    {
      "name": "revision_note",
      "label": "更正说明"
    },
    {
      "name": "locked",
      "label": "已确认"
    }
  ],
  "layout": "stack",
  "view": "table",
  "actions": [
    {
      "name": "record_coupon",
      "label": "登记冷却试片",
      "path": "/coupons/record-coupon",
      "fields": [
        {
          "name": "code",
          "label": "试片编号",
          "kind": "text",
          "initial": "GP-NEW"
        },
        {
          "name": "jig",
          "label": "弯模编号",
          "kind": "text",
          "initial": "CL-44"
        },
        {
          "name": "heat",
          "label": "保温温度 °C",
          "kind": "float",
          "initial": 520
        },
        {
          "name": "thick",
          "label": "片厚 mm",
          "kind": "float",
          "initial": 4
        },
        {
          "name": "target",
          "label": "目标弯度 mm",
          "kind": "float",
          "initial": 10
        },
        {
          "name": "measured",
          "label": "实测弯度 mm",
          "kind": "float",
          "initial": 8.4
        }
      ],
      "help": "冷却后以同一尺规记录目标和实弯。",
      "roles": [
        "operator",
        "reviewer"
      ],
      "success": "已写入"
    },
    {
      "name": "witness",
      "label": "确认尺规测量",
      "path": "/coupons/witness",
      "fields": [
        {
          "name": "coupon",
          "label": "试片编号",
          "kind": "text",
          "initial": "GP-NEW"
        }
      ],
      "help": "经复核员见证后才从待测转入训练账。",
      "roles": [
        "reviewer"
      ],
      "success": "已写入"
    },
    {
      "name": "correct_measured",
      "label": "更正冷却弯度（保留原读数）",
      "path": "/coupons/correct-measured",
      "fields": [
        {
          "name": "coupon",
          "label": "试片编号",
          "kind": "text",
          "initial": "GP-12"
        },
        {
          "name": "measured",
          "label": "更正后弯度 mm",
          "kind": "float",
          "initial": 8.1
        },
        {
          "name": "reason",
          "label": "更正原因",
          "kind": "text",
          "initial": "试片见证后复核发现冷却弯度抄错"
        }
      ],
      "help": "仅限已见证试片。更正在同一事务内作废受影响曲线并暂停待打样委托、释放机位；原读数保留在原始读数列与更正流水。",
      "roles": [
        "reviewer"
      ],
      "success": "已更正并留痕"
    },
    {
      "name": "coupon_revisions",
      "label": "查询试片更正流水",
      "path": "/coupons",
      "method": "get",
      "keyField": "coupon",
      "suffix": "/revisions",
      "fields": [
        {
          "name": "coupon",
          "label": "试片编号",
          "kind": "text",
          "initial": "GP-12"
        }
      ],
      "help": "查看该试片每次更正前后的读数、原因、操作人与时间。",
      "roles": [
        "operator",
        "reviewer",
        "viewer"
      ]
    }
  ]
};

        export const {title} = page;
        export const key = "coupons";
        export async function render(root, role) {
          await workspace(root, role, page);

        }
