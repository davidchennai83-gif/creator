import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Scheduler from '../src/pages/Scheduler';

const api = vi.hoisted(()=>({get:vi.fn(),post:vi.fn(),put:vi.fn(),delete:vi.fn()}));
vi.mock('../src/services/apiClient',()=>({default:api,errorMessage:()=> 'Request failed'}));
afterEach(()=>{cleanup();vi.resetAllMocks();});
const projects=[{id:'history',name:'Day of History'},{id:'indian-law',name:'Indian Law — Daily 5 Acts'}];
function setup() {
  api.get.mockImplementation(async (path:string)=>({data:{data:path.endsWith('/projects')?projects:[]}}));
  api.post.mockResolvedValue({data:{data:{id:'task'}}});
  render(<MemoryRouter><Scheduler/></MemoryRouter>);
}
it('New Task collects project, weekly days, dates, time and platform checkboxes',async()=>{
  setup();
  await waitFor(()=>expect(screen.getByRole('button',{name:'New Task'})).not.toBeDisabled());
  fireEvent.click(screen.getByRole('button',{name:'New Task'}));
  fireEvent.change(screen.getByLabelText('Task name'),{target:{value:'Morning law'}});
  fireEvent.change(screen.getByLabelText('Project'),{target:{value:'indian-law'}});
  fireEvent.click(screen.getByRole('button',{name:'weekly'}));
  fireEvent.click(screen.getByLabelText('Wed'));
  fireEvent.click(screen.getByLabelText('Facebook'));
  fireEvent.change(screen.getByLabelText('Generation time'),{target:{value:'08:00'}});
  fireEvent.click(screen.getByRole('button',{name:'Create task'}));
  await waitFor(()=>expect(api.post).toHaveBeenCalledWith('/scheduler',expect.objectContaining({name:'Morning law',project:'indian-law',frequency:'weekly',weekdays:[0,2],platforms:['facebook'],run_time:'08:00'})));
  expect(await screen.findByRole('status')).toHaveTextContent('Task saved');
});
it('Monthly and custom show their recurrence controls and Cancel does not save',async()=>{
  setup();
  await waitFor(()=>expect(screen.getByRole('button',{name:'New Task'})).not.toBeDisabled());
  fireEvent.click(screen.getByRole('button',{name:'New Task'}));
  fireEvent.click(screen.getByRole('button',{name:'monthly'}));
  expect(screen.getByLabelText('Day of month')).toBeVisible();
  fireEvent.click(screen.getByRole('button',{name:'custom'}));
  expect(screen.getByLabelText(/Repeat every/)).toBeVisible();
  fireEvent.click(screen.getByRole('button',{name:'Cancel'}));
  expect(api.post).not.toHaveBeenCalled();
});
