        import {workspace} from '../workspace.js';
        import {el} from '../dom.js';

        const page = {
  "title": "试制机位与打样见证",
  "module": "试制工位委托",
  "caption": "试制工位委托",
  "detail": "每个打样委托锁定唯一机位。拟合弯度或原始目标超过弯模量程时，委托保持未登记。曲线失效后待打样委托暂停并释放机位，已打样委托仍可查到原依据。",
  "path": "/work_orders",
  "columns": [
    {
      "name": "code",
      "label": "编号"
    },
    {
      "name": "profile",
      "label": "依据"
    },
    {
      "name": "jig",
      "label": "工位弯模"
    },
    {
      "name": "slot",
      "label": "机位时段"
    },
    {
      "name": "quantity",
      "label": "试片数"
    },
    {
      "name": "state",
      "label": "状态"
    }
  ],
  "layout": "flip",
  "view": "table",
  "actions": [
    {
      "name": "book_jig",
      "label": "分配机位",
      "path": "/work_orders/book-jig",
      "fields": [
        {
          "name": "code",
          "label": "委托号",
          "kind": "text",
          "initial": "JOB-24"
        },
        {
          "name": "profile",
          "label": "曲线版本",
          "kind": "text",
          "initial": "PRO-24"
        },
        {
          "name": "jig",
          "label": "工位弯模",
          "kind": "text",
          "initial": "CL-44"
        },
        {
          "name": "slot",
          "label": "唯一机位时段",
          "kind": "text",
          "initial": "11-24 15:30"
        },
        {
          "name": "quantity",
          "label": "试片数",
          "kind": "int",
          "initial": 3
        }
      ],
      "help": "输入一个尚未占用的时段。",
      "roles": [
        "operator",
        "reviewer"
      ],
      "success": "已写入"
    },
    {
      "name": "complete",
      "label": "签回打样见证",
      "path": "/work_orders/complete",
      "fields": [
        {
          "name": "order",
          "label": "委托号",
          "kind": "text",
          "initial": "JOB-24"
        },
        {
          "name": "witness",
          "label": "技师见证号",
          "kind": "text",
          "initial": "W-0302"
        }
      ],
      "help": "打样完成后记录技师凭证。",
      "roles": [
        "reviewer"
      ],
      "success": "已写入"
    },
    {
      "name": "order_basis",
      "label": "查询委托原依据",
      "path": "/work_orders",
      "method": "get",
      "keyField": "order",
      "suffix": "/basis",
      "fields": [
        {
          "name": "order",
          "label": "委托号",
          "kind": "text",
          "initial": "JOB-23"
        }
      ],
      "help": "回看委托所依据的曲线与基准试片；曲线已失效或委托已暂停时，原始读数仍可追溯。",
      "roles": [
        "operator",
        "reviewer",
        "viewer"
      ]
    }
  ]
};

        export const {title} = page;
        export const key = "work_orders";
        export async function render(root, role) {
          await workspace(root, role, page);

        }
