import { it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Input, Select } from '../src/components/common/Form';
import { Button } from '../src/components/common/Button';

it('labels are associated with their controls',()=>{
  render(<><Input label="Name" error="Required" /><Select label="Category" options={[{label:'Other',value:'other'}]} /></>);
  expect(screen.getByLabelText('Name')).toHaveAttribute('aria-invalid','true');
  expect(screen.getByLabelText('Category')).toHaveValue('other');
});
it('non-submit buttons do not accidentally submit forms',async()=>{
  const submit=vi.fn(e=>e.preventDefault());const click=vi.fn();
  render(<form onSubmit={submit}><Button onClick={click}>Cancel</Button></form>);
  await userEvent.click(screen.getByRole('button',{name:'Cancel'}));
  expect(click).toHaveBeenCalledOnce();expect(submit).not.toHaveBeenCalled();
});
