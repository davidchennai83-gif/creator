import { it, expect, vi } from 'vitest';
import axios from 'axios';
import api from '../src/services/apiClient';
import { useAuthStore } from '../src/stores/authStore';

it('API integration attaches the real session token and keeps a single v1 prefix',async()=>{
  useAuthStore.getState().setSession({id:'test',email:'test@example.com',username:'test',display_name:null,role:'EDITOR',is_active:true},'test-bearer');
  const original=api.defaults.adapter;
  const adapter=vi.fn(async config=>({data:{success:true,data:[]},status:200,statusText:'OK',headers:{},config}));
  api.defaults.adapter=adapter;
  try {
    await api.get('/scheduler');
    const config=adapter.mock.calls[0][0];
    expect(axios.getUri(config)).toBe('/api/v1/scheduler');
    expect(config.headers.Authorization).toBe('Bearer test-bearer');
  } finally {api.defaults.adapter=original;useAuthStore.getState().clear();}
});
