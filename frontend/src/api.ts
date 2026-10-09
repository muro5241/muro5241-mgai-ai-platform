export type User={id:string;email:string;name:string;role:'admin'|'member';active:boolean;credits:number;daily_request_limit:number;daily_token_limit:number};
export type Auth={user:User;csrf_token:string;nvidia_configured:boolean;commercial_mode:boolean;billing_enabled:boolean};
export type Workspace={id:string;name:string;description:string};
export type Model={id:string;is_default:boolean;name:string;license_name:string;license_url:string;enabled:boolean;access_verified:boolean;catalog_present:boolean;commercial_approved:boolean;price_input:string|null;price_output:string|null;pricing_reference:string|null};
export type Job={id:string;workspace_id:string;model_id:string;state:string;created_at:string;error_message:string|null;budget_tokens:number;cost_usd:string|null;result:{content:string;usage:{prompt_tokens:number;completion_tokens:number}|null;truncated:boolean}|null};
export type Usage={requests_24h:number;accounted_tokens_24h:number;reported_prompt_tokens:number;reported_completion_tokens:number;known_cost_usd:string;unverified_cost_jobs:number;credits:number;daily_request_limit:number;daily_token_limit:number};
export type Overview={users:number;workspaces:number;queue:number;usage:Usage;commercial_mode:boolean};
export type Audit={id:string;action:string;created_at:string};
export class ApiError extends Error{constructor(message:string,public status:number){super(message)}}
let csrf='';
export function setCsrf(token:string){csrf=token}
export async function api<T>(path:string,options:RequestInit={}):Promise<T>{
 const response=await fetch(path,{...options,credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf,...options.headers}});
 const data=await response.json();if(!response.ok)throw new ApiError(typeof data.detail==='string'?data.detail:'İstek tamamlanamadı.',response.status);return data;
}
export const states:Record<string,string>={queued:'Sırada',running:'Üretiliyor',succeeded:'Tamamlandı',failed:'Başarısız',uncertain:'Sonuç belirsiz',cancelled:'İptal edildi'};
export const activeState=(state:string)=>state==='queued'||state==='running';
export const costLabel=(cost:string|null)=>cost===null?'Doğrulanmadı':`$${Number(cost).toFixed(5)}`;

export const defaultModelId=(models:Model[])=>models.find(m=>m.is_default)?.id||models[0]?.id||'';
