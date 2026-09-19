document.querySelectorAll("textarea").forEach(x=>x.addEventListener("input",()=>{x.style.height="auto";x.style.height=x.scrollHeight+"px"}));
setTimeout(()=>{const t=document.querySelector(".toast");if(t)t.remove()},4000);
