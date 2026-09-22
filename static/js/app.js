document.querySelectorAll("textarea").forEach(x=>x.addEventListener("input",()=>{x.style.height="auto";x.style.height=x.scrollHeight+"px"}));
setTimeout(()=>{const t=document.querySelector(".toast");if(t)t.remove()},4000);

document.querySelectorAll('input[type="file"]').forEach(input=>{
  input.addEventListener("change",()=>{
    const label=input.closest(".drop");
    if(!label) return;

    const files=[...input.files];
    if(files.length===0) return;

    const strong=label.querySelector("strong");
    const small=label.querySelector("small");

    if(strong) strong.textContent="✅ Resume Uploaded";
    if(small) {
      small.textContent=files.length===1
        ? files[0].name
        : `${files.length} resumes selected`;
    }
  });
});
